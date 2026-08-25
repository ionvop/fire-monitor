import math
import os
import threading
import time
from datetime import datetime

import cv2
import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_socketio import SocketIO
from ultralytics import YOLO

from config import (
    CAPTURE_DIR,
    CAPTURE_ENABLED_DEFAULT,
    CAPTURE_MAX,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DEBUG_DISABLE_TRIGGER,
    FIRE_CONF_THRESHOLD,
    FIRE_TRACK_PIXELS_PER_DEGREE_Y,
    FIRE_TRACK_DEADBAND_PIXELS,
    FIRE_WAVE_AMPLITUDE,
    FIRE_WAVE_PERIOD,
    MIN_FIRE_DURATION,
    SCAN_X_MAX,
    SCAN_X_MIN,
    SCAN_Y_MAX,
    SCAN_Y_MIN,
    SCAN_CORNER_TOLERANCE,
    SERVO_IP,
    WEBCAM_INDEX,
)

SERVO_BASE_URL = f"http://{SERVO_IP}"
DASHBOARD_DIR = "dashboard"
DIST_DIR = os.path.join(DASHBOARD_DIR, "dist")

# The ESP32 moves the servo 1 degree every MOVE_INTERVAL (20 ms).
DEGREE_MOVE_SECONDS = 0.02

app = Flask(__name__, static_folder=None)
socketio = SocketIO(app, cors_allowed_origins="*")

# Shared state between the detection thread and the web server.
state_lock = threading.Lock()
latest_frame = None          # JPEG bytes of the annotated frame
auto_mode = True             # True = automatic scanning; False = manual control
auto_fire = True             # Auto-fire on detection (only relevant in manual mode)
fire_active = False          # True while the trigger is firing
capture_enabled = CAPTURE_ENABLED_DEFAULT  # Auto-save fire screenshots


# ---------------------------------------------------------------------------
# Servo controller helpers
# ---------------------------------------------------------------------------
def servo_get(path, params=None, timeout=1.0):
    try:
        return requests.get(f"{SERVO_BASE_URL}{path}", params=params, timeout=timeout)
    except requests.RequestException as exc:
        print(f"Servo request failed ({path}): {exc}")
        return None


def stop_all_movement():
    """Stop any continuous movement on both axes."""
    for axis in ("x", "y"):
        for direction in ("left", "right", "up", "down"):
            servo_get(
                "/api/move",
                {"axis": axis, "dir": direction, "cmd": "stop"},
            )


def fire_trigger():
    """Fire the physical trigger, unless disabled by the debug config.

    When DEBUG_DISABLE_TRIGGER is True, the trigger is never fired (used for
    debugging detection/tracking without the turret actually firing). The safe
    "retract" state is unaffected.
    """
    if DEBUG_DISABLE_TRIGGER:
        print("DEBUG_DISABLE_TRIGGER is set; skipping trigger fire.")
        return
    servo_get("/api/servo/trigger", {"state": "fire"})


def get_status():
    """Return the current servo angles as a dict, or None on failure."""
    resp = servo_get("/api/status")
    if resp is None or resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def center_servos():
    """Center both servos at (90, 90) on startup."""
    # Stop any continuous movement left over from a previous session.
    stop_all_movement()

    status = get_status()

    if status is None:
        print("Could not read servo status; skipping centering.")
        return

    servo_get("/api/servo/x", {"angle": 90})
    servo_get("/api/servo/y", {"angle": 90})


# ---------------------------------------------------------------------------
# Fire screenshot capture
# ---------------------------------------------------------------------------
def _capture_dir():
    """Return the absolute path to the capture directory, creating it if needed."""
    path = os.path.abspath(CAPTURE_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def list_captures():
    """Return a list of capture dicts (filename, timestamp), newest first."""
    path = _capture_dir()
    captures = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if not os.path.isfile(full) or not name.lower().endswith(".jpg"):
            continue
        try:
            ts = datetime.fromtimestamp(os.path.getmtime(full)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except OSError:
            ts = ""
        captures.append({"filename": name, "timestamp": ts})
    captures.sort(key=lambda c: c["filename"], reverse=True)
    return captures


def _enforce_capture_limit():
    """Delete the oldest captures so at most CAPTURE_MAX remain."""
    path = _capture_dir()
    files = sorted(
        (os.path.join(path, name) for name in os.listdir(path)
         if name.lower().endswith(".jpg")),
        key=os.path.getmtime,
    )
    while len(files) > CAPTURE_MAX:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
        except OSError:
            pass


def save_capture(frame):
    """Save an annotated frame as a JPEG capture and enforce the size cap.

    Returns the filename on success, or None on failure.
    """
    if frame is None:
        return None
    path = _capture_dir()
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    full = os.path.join(path, filename)
    # Avoid collisions if two events land in the same second.
    counter = 1
    while os.path.exists(full):
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{counter}.jpg"
        full = os.path.join(path, filename)
        counter += 1
    ok, jpeg = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    try:
        with open(full, "wb") as f:
            f.write(jpeg.tobytes())
    except OSError as exc:
        print(f"Failed to save capture: {exc}")
        return None
    _enforce_capture_limit()
    print(f"Saved fire capture: {filename}")
    return filename


def delete_capture(filename):
    """Delete a single capture file. Returns True if it was removed."""
    path = _capture_dir()
    full = os.path.join(path, os.path.basename(filename))
    if not os.path.isfile(full):
        return False
    try:
        os.remove(full)
        return True
    except OSError:
        return False


def clear_captures():
    """Delete all capture files. Returns the number removed."""
    path = _capture_dir()
    removed = 0
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isfile(full) and name.lower().endswith(".jpg"):
            try:
                os.remove(full)
                removed += 1
            except OSError:
                pass
    return removed


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
        self._x_moving = False
        self._y_moving = False

    def _set_x(self, direction):
        """Start moving X in `direction` (or stop if None)."""
        if direction is None:
            if self._x_moving:
                servo_get("/api/move", {"axis": "x", "dir": "left", "cmd": "stop"})
                servo_get("/api/move", {"axis": "x", "dir": "right", "cmd": "stop"})
                self._x_moving = False
            return
        servo_get("/api/move", {"axis": "x", "dir": direction, "cmd": "start"})
        self._x_moving = True

    def _set_y(self, direction):
        """Start moving Y in `direction` (or stop if None)."""
        if direction is None:
            if self._y_moving:
                servo_get("/api/move", {"axis": "y", "dir": "up", "cmd": "stop"})
                servo_get("/api/move", {"axis": "y", "dir": "down", "cmd": "stop"})
                self._y_moving = False
            return
        servo_get("/api/move", {"axis": "y", "dir": direction, "cmd": "start"})
        self._y_moving = True

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


# ---------------------------------------------------------------------------
# Fire detection & control loop
# ---------------------------------------------------------------------------
def track_fire(boxes, frame_shape, current_time, fire_start_time):
    """Continuously steer the turret toward the fire and wave Y while firing.

    Only called in automatic mode while a fire is actively detected. Computes
    the fire bbox center in pixels and its offset from the frame center. As
    long as the fire is outside the configured deadzone (FIRE_TRACK_DEADBAND_
    PIXELS), it issues continuous /api/move commands so the turret keeps
    moving toward the fire instead of jumping to an absolute angle. Once the
    fire is within the deadzone on both axes, all movement stops. The Y axis
    also oscillates around the fire's vertical center using a sine wave so the
    turret sweeps up and down while firing.

    Returns True if a fire was found and tracking commands were issued.
    """
    if boxes is None:
        return False

    # Pick the highest-confidence fire detection.
    best = None
    best_conf = 0.0
    for box in boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        if cls == 0 and conf > FIRE_CONF_THRESHOLD and conf > best_conf:
            best = box
            best_conf = conf
    if best is None:
        return False

    # Fire bbox center in pixels.
    x1, y1, x2, y2 = (float(v) for v in best.xyxy[0])
    fire_cx = (x1 + x2) / 2.0
    fire_cy = (y1 + y2) / 2.0

    # Frame center in pixels.
    height, width = frame_shape[:2]
    frame_cx = width / 2.0
    frame_cy = height / 2.0

    status = get_status()
    if status is None:
        return False
    cur_x = status.get("x", 90)
    cur_y = status.get("y", 90)

    # Pixel offset of the fire from the frame center.
    dx = fire_cx - frame_cx
    dy = fire_cy - frame_cy

    # Once the fire is within the deadzone on both axes, stop and hold.
    if (abs(dx) <= FIRE_TRACK_DEADBAND_PIXELS
            and abs(dy) <= FIRE_TRACK_DEADBAND_PIXELS):
        stop_all_movement()
        return True

    # X axis: keep moving toward the fire horizontally while it is off-center.
    if abs(dx) > FIRE_TRACK_DEADBAND_PIXELS:
        direction = "right" if dx > 0 else "left"
        servo_get("/api/move", {"axis": "x", "dir": direction, "cmd": "start"})
    else:
        servo_get("/api/move", {"axis": "x", "dir": "left", "cmd": "stop"})
        servo_get("/api/move", {"axis": "x", "dir": "right", "cmd": "stop"})

    # Y axis: convert the vertical offset to degrees and add the wave, then
    # move up/down toward the resulting target while the fire is off-center.
    centered_y = cur_y + dy / FIRE_TRACK_PIXELS_PER_DEGREE_Y
    if fire_start_time is not None:
        elapsed = current_time - fire_start_time
        wave = FIRE_WAVE_AMPLITUDE * math.sin(
            2.0 * math.pi * elapsed / FIRE_WAVE_PERIOD
        )
    else:
        wave = 0.0
    target_y = centered_y + wave

    if abs(dy) > FIRE_TRACK_DEADBAND_PIXELS:
        direction = "up" if target_y > cur_y else "down"
        servo_get("/api/move", {"axis": "y", "dir": direction, "cmd": "start"})
    else:
        servo_get("/api/move", {"axis": "y", "dir": "up", "cmd": "stop"})
        servo_get("/api/move", {"axis": "y", "dir": "down", "cmd": "stop"})

    return True


def detection_loop(model, cap):
    global latest_frame, fire_active

    scanner = RoomScanner()
    last_state = None
    fire_start_time = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame")
            time.sleep(0.1)
            continue

        results = model(frame, imgsz=640)
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

        fire_detected = False
        boxes = results[0].boxes
        if boxes is not None:
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                if cls == 0 and conf > FIRE_CONF_THRESHOLD:
                    fire_detected = True
                    break

        with state_lock:
            auto = auto_mode
            auto_fire_enabled = auto_fire
            capture_on = capture_enabled

        current_time = time.monotonic()

        # Automatic fire-on-detection. In automatic mode it is always enabled;
        # in manual mode it follows the auto_fire toggle.
        if fire_detected and (auto or auto_fire_enabled):
            if last_state != "fire":
                scanner.stop()
                fire_trigger()
                fire_start_time = current_time
                last_state = "fire"
                with state_lock:
                    fire_active = True
                # Save a screenshot of the annotated frame on first detection.
                if capture_on:
                    save_capture(annotated_frame)

            # In automatic mode, center on the fire and wave Y up/down while
            # firing. Manual mode keeps the old stop-and-fire-in-place behavior.
            if auto:
                track_fire(boxes, frame.shape, current_time, fire_start_time)
        else:
            if last_state == "fire":
                if fire_start_time is not None and (current_time - fire_start_time) >= MIN_FIRE_DURATION:
                    servo_get("/api/servo/trigger", {"state": "retract"})
                    last_state = "retract"
                    fire_start_time = None
                    with state_lock:
                        fire_active = False
            elif last_state != "retract":
                servo_get("/api/servo/trigger", {"state": "retract"})
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

    center_servos()

    detection_thread = threading.Thread(
        target=detection_loop,
        args=(model, cap),
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
        servo_get("/api/servo/trigger", {"state": "retract"})
        cap.release()


if __name__ == "__main__":
    main()