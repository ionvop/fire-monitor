import os
import threading
import time
from datetime import datetime

import cv2
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from ultralytics import YOLO

from config import (
    CAPTURE_ENABLED_DEFAULT,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DEBUG_DISABLE_TRIGGER,
    FIRE_CONF_THRESHOLD,
    MIN_FIRE_DURATION,
    SCAN_X_MAX,
    SCAN_X_MIN,
    SCAN_Y_MAX,
    SCAN_Y_MIN,
    SCAN_CORNER_TOLERANCE,
    SERVO_IP,
    THERMAL_ENABLED,
    THERMAL_FAIL_OPEN,
    THERMAL_FLIP_X,
    THERMAL_FLIP_Y,
    THERMAL_HTTP_TIMEOUT,
    THERMAL_POLL_INTERVAL,
    THERMAL_THRESHOLD_C,
    THERMAL_TRACK_DEADBAND_PIXELS,
    THERMAL_TRACK_SETTLE_TIMEOUT,
    THERMAL_TRACK_STEP_DEGREES,
    WEBCAM_INDEX,
)
from alerts import enqueue_fire_report, start_alert_worker, stop_alert_worker
from captures import (
    clear_captures,
    delete_capture,
    enqueue_capture,
    list_captures,
    start_capture_worker,
    stop_capture_worker,
    _capture_dir,
)
from servo import ServoClient, servo_get as _servo_get
from thermal import ThermalSensor

SERVO_BASE_URL = f"http://{SERVO_IP}"
DASHBOARD_DIR = "dashboard"
DIST_DIR = os.path.join(DASHBOARD_DIR, "dist")

app = Flask(__name__, static_folder=None)
socketio = SocketIO(app, cors_allowed_origins="*")

# Non-blocking servo client. All movement/trigger commands are queued to a
# background worker and the latest angles are cached by a status poller, so the
# detection loop never blocks on servo HTTP requests.
servo_client = ServoClient(SERVO_BASE_URL)

# Shared state between the detection thread and the web server.
state_lock = threading.Lock()
latest_frame = None          # JPEG bytes of the annotated frame
auto_mode = True             # True = automatic scanning; False = manual control
auto_fire = False            # Auto-fire on detection (only relevant in manual mode)
fire_active = False          # True while the trigger is firing
capture_enabled = CAPTURE_ENABLED_DEFAULT  # Auto-save fire screenshots

# Fire detection confidence threshold. Seeded from config on startup and
# adjustable at runtime from the dashboard. Only these preset values are
# accepted by the /api/threshold route.
FIRE_CONF_PRESETS = {"high": 0.85, "medium": 0.7, "low": 0.6}
fire_conf_threshold = FIRE_CONF_THRESHOLD

# Latest AMG8833 thermal reading, shared between the detection thread and the
# web server. max_temp_c is the hottest pixel temperature (None if unavailable
# or stale); thermal_ok is whether it clears the configured threshold;
# thermal_row/thermal_col are the hottest pixel's 0-based grid coordinates
# (None if unavailable or stale), used to aim the turret.
thermal_max_temp_c = None
thermal_ok = False
thermal_row = None
thermal_col = None


# ---------------------------------------------------------------------------
# Servo controller helpers
# ---------------------------------------------------------------------------
def servo_get(path, params=None, timeout=1.0):
    """Blocking servo GET, used only by the Flask routes (own thread)."""
    return _servo_get(SERVO_BASE_URL, path, params, timeout)


def stop_all_movement():
    """Stop any continuous movement on both axes (non-blocking)."""
    servo_client.stop_all()


def fire_trigger():
    """Fire the physical trigger, unless disabled by the debug config.

    When DEBUG_DISABLE_TRIGGER is True, the trigger is never fired (used for
    debugging detection/tracking without the turret actually firing). The safe
    "retract" state is unaffected.
    """
    if DEBUG_DISABLE_TRIGGER:
        print("DEBUG_DISABLE_TRIGGER is set; skipping trigger fire.")
        return
    servo_client.trigger("fire")


def get_status():
    """Return the latest cached servo angles as a dict, or None if unknown."""
    return servo_client.get_status()


def center_servos():
    """Center both servos at (90, 90) on startup."""
    # Stop any continuous movement left over from a previous session.
    stop_all_movement()

    status = get_status()

    if status is None:
        print("Could not read servo status; skipping centering.")
        return

    servo_client.set_angle("x", 90)
    servo_client.set_angle("y", 90)


# ---------------------------------------------------------------------------
# Fire screenshot capture
# ---------------------------------------------------------------------------
# Capture helpers (list/delete/clear/save) live in captures.py; the blocking
# save runs on a background worker via enqueue_capture().


# ---------------------------------------------------------------------------
# Automatic scanning
# ---------------------------------------------------------------------------
class RoomScanner:
    """Scans the room by sweeping each direction until it hits an edge.

    The ESP32 moves continuously while a movement flag is set, so the scanner
    keeps the desired direction active and only issues a stop when it needs to
    reverse or pause. It polls /api/status to learn the current angles.

    The scan follows a simple repeating pattern, holding each direction until
    the corresponding edge (defined by the configured x/y min/max) is reached:
        up -> right -> down -> left -> repeat
    """

    def __init__(self):
        # Direction index into the up/right/down/left cycle. "Up" is increasing
        # Y (toward SCAN_Y_MAX), so the top edge sits at SCAN_Y_MAX.
        self._direction_index = 0

    @property
    def direction(self):
        """The current scan direction: 'up', 'right', 'down', or 'left'."""
        return ("up", "right", "down", "left")[self._direction_index]

    def _set_x(self, direction):
        """Start moving X in `direction` (or stop if None)."""
        if direction is None:
            servo_client.stop_axis("x")
        else:
            servo_client.set_move("x", direction)

    def _set_y(self, direction):
        """Start moving Y in `direction` (or stop if None)."""
        if direction is None:
            servo_client.stop_axis("y")
        else:
            servo_client.set_move("y", direction)

    def stop(self):
        """Stop all scanning movement."""
        self._set_x(None)
        self._set_y(None)

    def step(self):
        """Advance the scan by one poll interval."""
        status = get_status()
        if status is None:
            return

        x = status.get("x", 90)
        y = status.get("y", 90)

        # Check whether the current direction has reached its edge.
        reached_edge = False
        if self._direction_index == 0:      # up
            reached_edge = y >= SCAN_Y_MAX - SCAN_CORNER_TOLERANCE
        elif self._direction_index == 1:    # right
            reached_edge = x >= SCAN_X_MAX - SCAN_CORNER_TOLERANCE
        elif self._direction_index == 2:    # down
            reached_edge = y <= SCAN_Y_MIN + SCAN_CORNER_TOLERANCE
        else:                               # left
            reached_edge = x <= SCAN_X_MIN + SCAN_CORNER_TOLERANCE

        if reached_edge:
            self._direction_index = (self._direction_index + 1) % 4

        # Move one axis at a time for the current direction so the turret
        # traces clean right-angle edges (no diagonal cutting).
        if self._direction_index == 0:      # up
            self._set_y("up")
            self._set_x(None)
        elif self._direction_index == 1:    # right
            self._set_x("right")
            self._set_y(None)
        elif self._direction_index == 2:    # down
            self._set_y("down")
            self._set_x(None)
        else:                               # left
            self._set_x("left")
            self._set_y(None)


# The automatic room scanner. Created at module scope so the web server thread
# can read its current direction for the dashboard indicator.
scanner = RoomScanner()


# ---------------------------------------------------------------------------
# Fire detection & control loop
# ---------------------------------------------------------------------------
def track_thermal(row, col):
    """Steer the turret toward the thermal hottest pixel by microadjusting.

    Only called in automatic mode while the thermal trigger is active (the
    hottest pixel clears the threshold). The AMG8833 reports an 8x8 grid; the
    hottest pixel's (row, col) is compared to the grid center (3.5, 3.5).

    Unlike the previous continuous-movement approach, this reads the turret's
    current X/Y angle from the cached /api/status, nudges each off-center axis
    by THERMAL_TRACK_STEP_DEGREES using an absolute move, waits for the ESP32 to
    report the new angle (up to THERMAL_TRACK_SETTLE_TIMEOUT), then the caller
    compares again on the next loop iteration. An axis within
    THERMAL_TRACK_DEADBAND_PIXELS of center is left untouched.

    THERMAL_FLIP_X / THERMAL_FLIP_Y invert the mapping for a rotated or
    mirrored sensor mount.

    Returns True if a hot pixel was available and tracking commands were
    issued, or False if no fresh thermal reading is available.
    """
    if row is None or col is None:
        return False

    status = get_status()
    if status is None:
        # No known turret position; cannot compute an absolute target.
        return False

    # Offset of the hot pixel from the grid center (3.5, 3.5).
    dx = col - 3.5
    dy = row - 3.5
    if THERMAL_FLIP_X:
        dx = -dx
    if THERMAL_FLIP_Y:
        dy = -dy

    # X axis: nudge toward the hot pixel horizontally while off-center.
    # dx > 0 means the hot pixel is to the right, so increase the X angle.
    if abs(dx) > THERMAL_TRACK_DEADBAND_PIXELS:
        current_x = status.get("x")
        if current_x is not None:
            target_x = max(0, min(180, current_x + (
                THERMAL_TRACK_STEP_DEGREES if dx > 0 else -THERMAL_TRACK_STEP_DEGREES
            )))
            if target_x != current_x:
                servo_client.set_angle("x", target_x)
                servo_client.wait_for_angle("x", target_x, THERMAL_TRACK_SETTLE_TIMEOUT)

    # Y axis: nudge toward the hot pixel vertically while off-center.
    # dy > 0 means the hot pixel is below the grid center, so the camera must
    # tilt down to follow it; dy < 0 means it is above, so tilt up. The API
    # convention is "higher = up", so tilting down decreases the Y angle.
    if abs(dy) > THERMAL_TRACK_DEADBAND_PIXELS:
        current_y = status.get("y")
        if current_y is not None:
            target_y = max(0, min(180, current_y + (
                -THERMAL_TRACK_STEP_DEGREES if dy > 0 else THERMAL_TRACK_STEP_DEGREES
            )))
            if target_y != current_y:
                servo_client.set_angle("y", target_y)
                servo_client.wait_for_angle("y", target_y, THERMAL_TRACK_SETTLE_TIMEOUT)

    return True


def detection_loop(model, cap, thermal_sensor=None):
    global latest_frame, fire_active, scanner
    global thermal_max_temp_c, thermal_ok, thermal_row, thermal_col

    scanner = RoomScanner()
    last_state = None
    fire_start_time = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            time.sleep(0.1)
            continue

        # Read the current fire confidence threshold before inference so the
        # preview only annotates confident fire detections. Passing conf and
        # classes to the model means results[0].plot() below draws only class-0
        # (fire) boxes above the threshold. This is preview-only: the webcam
        # detection no longer gates aiming or firing (the thermal sensor does).
        with state_lock:
            threshold = fire_conf_threshold
        results = model(frame, imgsz=640, conf=threshold, classes=[0])
        annotated_frame = results[0].plot()

        # Overlay the current datetime on the annotated frame.
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            annotated_frame,
            timestamp,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        # Publish the annotated frame for the dashboard stream.
        _, jpeg = cv2.imencode(".jpg", annotated_frame)
        with state_lock:
            latest_frame = jpeg.tobytes()

        with state_lock:
            auto = auto_mode
            auto_fire_enabled = auto_fire
            capture_on = capture_enabled

        # Read the AMG8833 thermal verdict. The thermal sensor is the sole
        # trigger for aiming and firing: the hottest pixel must clear the
        # threshold. The webcam/YOLO results above are used only to annotate the
        # dashboard preview and no longer gate the trigger. The hottest pixel's
        # row/col is published and used below to aim the turret.
        max_temp_c = None
        thermal_row_reading = None
        thermal_col_reading = None
        thermal_trigger = False
        if thermal_sensor is not None:
            max_temp_c, ok, thermal_row_reading, thermal_col_reading = (
                thermal_sensor.read()
            )
            with state_lock:
                thermal_max_temp_c = max_temp_c
                thermal_ok = ok
                thermal_row = thermal_row_reading
                thermal_col = thermal_col_reading
            # Require a fresh reading (row/col present) so a fail-open sensor
            # that is unavailable does not trigger firing.
            thermal_trigger = (
                THERMAL_ENABLED
                and ok
                and thermal_row_reading is not None
                and thermal_col_reading is not None
            )

        current_time = time.monotonic()

        # Automatic fire-on-detection, driven solely by the thermal verdict. In
        # automatic mode it is always enabled; in manual mode it follows the
        # auto_fire toggle.
        if thermal_trigger and (auto or auto_fire_enabled):
            if last_state != "fire":
                scanner.stop()
                fire_trigger()
                fire_start_time = current_time
                last_state = "fire"
                with state_lock:
                    fire_active = True
                # Save a screenshot of the annotated frame on first detection.
                # The frame is copied so the background worker can encode it
                # while the loop reuses its buffer.
                if capture_on:
                    enqueue_capture(annotated_frame.copy())
                # Report the detection to the remote backend (logs to
                # fire_history and pushes to subscribers, subject to cooldown).
                # Queued to a worker so the loop never blocks on the network.
                enqueue_fire_report("detected", max_temp_c)

            # In automatic mode, aim at the thermal hottest pixel while firing.
            # Manual mode keeps the old stop-and-fire-in-place behavior. If no
            # fresh thermal reading is available, stop rather than drift.
            if auto:
                if not track_thermal(thermal_row_reading, thermal_col_reading):
                    stop_all_movement()
        else:
            if last_state == "fire":
                # The fire is no longer detected. Stop any continuous movement
                # (e.g. leftover scanning) so the turret doesn't keep drifting
                # before scanning resumes. Absolute tracking leaves no
                # continuous movement running, so this is a safe no-op there.
                stop_all_movement()
                if fire_start_time is not None and (current_time - fire_start_time) >= MIN_FIRE_DURATION:
                    servo_client.trigger("retract")
                    last_state = "retract"
                    fire_start_time = None
                    with state_lock:
                        fire_active = False
                    # Report the retraction so the PWA marks the alert resolved.
                    # At most one retraction is logged per cooldown window.
                    enqueue_fire_report("retracted", max_temp_c)
            elif last_state != "retract":
                servo_client.trigger("retract")
                last_state = "retract"

        # Automatic scanning only in automatic mode and when no fire is active.
        if auto and not fire_active and last_state != "fire":
            scanner.step()
        else:
            scanner.stop()

        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Web server routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(DIST_DIR, "index.html")


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(os.path.join(DIST_DIR, "assets"), filename)


@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            with state_lock:
                frame = latest_frame
            if frame is not None:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(0.03)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/status")
def api_status():
    status = get_status()
    if status is None:
        return jsonify({"error": "Servo controller unreachable"}), 502
    with state_lock:
        status["auto_mode"] = auto_mode
        status["auto_fire"] = auto_fire
        status["fire_active"] = fire_active
        status["capture_enabled"] = capture_enabled
        status["fire_conf_threshold"] = fire_conf_threshold
        status["scan_direction"] = scanner.direction
        status["thermal_enabled"] = THERMAL_ENABLED
        status["thermal_threshold_c"] = THERMAL_THRESHOLD_C
        status["max_temp_c"] = thermal_max_temp_c
        status["thermal_ok"] = thermal_ok
        status["thermal_row"] = thermal_row
        status["thermal_col"] = thermal_col
    return jsonify(status)


@app.route("/api/move")
def api_move():
    axis = request.args.get("axis")
    direction = request.args.get("dir")
    cmd = request.args.get("cmd")
    if not all((axis, direction, cmd)):
        return jsonify({"error": "Missing axis, dir, or cmd"}), 400
    with state_lock:
        if auto_mode:
            return jsonify({"error": "Turret is in automatic mode. Manual controls are disabled."}), 403
    resp = servo_get("/api/move", {"axis": axis, "dir": direction, "cmd": cmd})
    if resp is None:
        return jsonify({"error": "Servo controller unreachable"}), 502
    return resp.text, resp.status_code


@app.route("/api/servo/trigger")
def api_trigger():
    state = request.args.get("state")
    if state not in ("fire", "retract"):
        return jsonify({"error": "Invalid state. Use fire or retract"}), 400
    with state_lock:
        if auto_mode:
            return jsonify({"error": "Turret is in automatic mode. Manual controls are disabled."}), 403
    if state == "fire" and DEBUG_DISABLE_TRIGGER:
        return jsonify({"error": "Trigger firing is disabled by DEBUG_DISABLE_TRIGGER."}), 403
    resp = servo_get("/api/servo/trigger", {"state": state})
    if resp is None:
        return jsonify({"error": "Servo controller unreachable"}), 502
    return resp.text, resp.status_code


@app.route("/api/mode", methods=["POST"])
def api_mode():
    """Switch between automatic and manual mode.

    JSON body:
        {"mode": "auto" | "manual", "auto_fire": true | false (optional)}
    """
    global auto_mode, auto_fire
    data = request.get_json(silent=True) or {}
    mode = data.get("mode")

    if mode not in ("auto", "manual"):
        return jsonify({"error": "Invalid mode. Use 'auto' or 'manual'"}), 400

    with state_lock:
        auto_mode = mode == "auto"
        if "auto_fire" in data:
            if not isinstance(data["auto_fire"], bool):
                return jsonify({"error": "auto_fire must be a boolean"}), 400
            auto_fire = data["auto_fire"]

    # Switching to manual mode stops any scanning movement.
    if not auto_mode:
        stop_all_movement()

    return jsonify({"auto_mode": auto_mode, "auto_fire": auto_fire})


@app.route("/api/servo/x")
def api_servo_x():
    angle = request.args.get("angle")
    if angle is None:
        return jsonify({"error": "Missing angle parameter"}), 400
    resp = servo_get("/api/servo/x", {"angle": angle})
    if resp is None:
        return jsonify({"error": "Servo controller unreachable"}), 502
    return resp.text, resp.status_code


@app.route("/api/servo/y")
def api_servo_y():
    angle = request.args.get("angle")
    if angle is None:
        return jsonify({"error": "Missing angle parameter"}), 400
    resp = servo_get("/api/servo/y", {"angle": angle})
    if resp is None:
        return jsonify({"error": "Servo controller unreachable"}), 502
    return resp.text, resp.status_code


# ---------------------------------------------------------------------------
# Fire screenshot capture routes
# ---------------------------------------------------------------------------
@app.route("/api/capture/status")
def api_capture_status():
    with state_lock:
        return jsonify({"enabled": capture_enabled})


@app.route("/api/capture", methods=["POST"])
def api_capture_toggle():
    """Enable or disable automatic fire screenshot capture.

    JSON body:
        {"enabled": true | false}
    """
    global capture_enabled
    data = request.get_json(silent=True) or {}
    enabled = data.get("enabled")
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled must be a boolean"}), 400
    with state_lock:
        capture_enabled = enabled
    return jsonify({"enabled": capture_enabled})


@app.route("/api/threshold", methods=["POST"])
def api_threshold():
    """Set the fire detection confidence threshold.

    Only the preset values in FIRE_CONF_PRESETS are accepted.

    JSON body:
        {"threshold": 0.85 | 0.7 | 0.6}
    """
    global fire_conf_threshold
    data = request.get_json(silent=True) or {}
    threshold = data.get("threshold")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return jsonify({"error": "threshold must be a number"}), 400
    threshold = float(threshold)
    if threshold not in FIRE_CONF_PRESETS.values():
        return jsonify({"error": "threshold must be one of the preset values"}), 400
    with state_lock:
        fire_conf_threshold = threshold
    return jsonify({"threshold": fire_conf_threshold})


@app.route("/api/captures")
def api_captures():
    return jsonify({"captures": list_captures()})


@app.route("/captures/<path:filename>")
def api_capture_image(filename):
    return send_from_directory(_capture_dir(), filename)


@app.route("/api/captures/<path:filename>", methods=["DELETE"])
def api_capture_delete(filename):
    if delete_capture(filename):
        return jsonify({"deleted": filename})
    return jsonify({"error": "Capture not found"}), 404


@app.route("/api/captures", methods=["DELETE"])
def api_captures_clear():
    removed = clear_captures()
    return jsonify({"deleted": removed})


# ---------------------------------------------------------------------------
# WebSocket presence handling
# ---------------------------------------------------------------------------
@socketio.on("connect")
def on_connect():
    print("Dashboard user connected")


@socketio.on("disconnect")
def on_disconnect():
    print("Dashboard user disconnected")


def main():
    model = YOLO("best.pt")
    cap = cv2.VideoCapture(WEBCAM_INDEX)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    print(f"Dashboard available at http://localhost:{DASHBOARD_PORT}")

    # AMG8833 thermal layer. The sensor is wired to the servo ESP32 and polled
    # over the AP network. It is the sole trigger for aiming and firing: the
    # hottest pixel must clear the threshold, and the turret steers toward that
    # pixel. The webcam/YOLO pipeline only annotates the dashboard preview. If
    # the endpoint is unreachable, the controller still boots and thermal_ok
    # follows THERMAL_FAIL_OPEN (but no fresh reading means no trigger).
    thermal_sensor = ThermalSensor(
        base_url=SERVO_BASE_URL,
        threshold_c=THERMAL_THRESHOLD_C,
        poll_interval=THERMAL_POLL_INTERVAL,
        http_timeout=THERMAL_HTTP_TIMEOUT,
        fail_open=THERMAL_FAIL_OPEN,
    )
    if not thermal_sensor.available:
        print(
            "Thermal sensor unavailable; "
            f"fail-open={THERMAL_FAIL_OPEN}, enabled={THERMAL_ENABLED}"
        )

    # Start the background workers that keep blocking I/O off the detection
    # loop: alert log/push and fire screenshot saving.
    start_alert_worker()
    start_capture_worker()

    center_servos()

    detection_thread = threading.Thread(
        target=detection_loop,
        args=(model, cap, thermal_sensor),
        daemon=True,
    )
    detection_thread.start()

    try:
        socketio.run(
            app,
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            debug=False,
            use_reloader=False,
        )
    finally:
        stop_all_movement()
        servo_client.trigger("retract")
        stop_alert_worker()
        stop_capture_worker()
        servo_client.close()
        thermal_sensor.close()
        cap.release()


if __name__ == "__main__":
    main()