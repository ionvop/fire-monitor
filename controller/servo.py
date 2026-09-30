"""Asynchronous servo controller client.

The ESP32 servo controller is reached over HTTP. Issuing those requests
directly from the detection loop blocks it (each request can take up to the
configured timeout), which stalls fire tracking. This module moves all servo
I/O onto background threads:

* A **command worker** drains a bounded queue of command batches and issues
  the HTTP requests in order. Producers never block.
* A **status poller** periodically GETs ``/api/status`` and caches the latest
  angles, so ``get_status()`` is a non-blocking cache read.

Movement commands are *coalesced*: the client tracks the desired direction per
axis and only enqueues a batch when that desired state actually changes. A slow
or unreachable ESP32 therefore cannot build a backlog of redundant moves.

Because coalescing means a single dropped/ignored HTTP request would leave the
turret stuck, the command worker also *re-asserts* the current desired movement
state to the ESP32 every ``SERVO_MOVE_REFRESH_INTERVAL`` seconds. This keeps the
servo continuously informed of which direction to move even if a command was
lost, without flooding it with per-frame requests.

The module-level ``servo_get`` helper is kept for the Flask routes, which run
on their own thread and may block harmlessly.
"""

import queue
import threading
import time

import requests

from config import (
    SCAN_STATUS_POLL_INTERVAL,
    SERVO_CMD_QUEUE_MAX,
    SERVO_HTTP_TIMEOUT,
    SERVO_MOVE_REFRESH_INTERVAL,
    THERMAL_TRACK_SETTLE_POLL,
)

# Directions that stop each axis (both are sent to halt continuous movement).
_AXIS_STOP_DIRS = {
    "x": ("left", "right"),
    "y": ("up", "down"),
}


def servo_get(base_url, path, params=None, timeout=SERVO_HTTP_TIMEOUT):
    """Issue a single blocking GET to the servo controller.

    Returns the ``requests.Response``, or None on a request failure.
    """
    try:
        return requests.get(f"{base_url}{path}", params=params, timeout=timeout)
    except requests.RequestException as exc:
        print(f"Servo request failed ({path}): {exc}")
        return None


class ServoClient:
    """Non-blocking front-end for the ESP32 servo controller.

    Producers call ``set_move`` / ``stop_axis`` / ``stop_all`` / ``trigger`` /
    ``set_angle``; each enqueues a batch of HTTP commands for the worker thread.
    ``get_status`` returns the most recent cached ``/api/status`` payload.
    """

    def __init__(self, base_url, http_timeout=SERVO_HTTP_TIMEOUT,
                 status_poll_interval=SCAN_STATUS_POLL_INTERVAL,
                 queue_max=SERVO_CMD_QUEUE_MAX,
                 move_refresh_interval=SERVO_MOVE_REFRESH_INTERVAL):
        self._base_url = base_url.rstrip("/")
        self._http_timeout = http_timeout
        self._status_poll_interval = status_poll_interval
        self._move_refresh_interval = move_refresh_interval

        self._queue = queue.Queue(maxsize=queue_max)
        self._stop = threading.Event()

        # Desired continuous-movement direction per axis (None = stopped).
        self._desired = {"x": None, "y": None}
        self._desired_lock = threading.Lock()

        # Latest cached status payload.
        self._status = None
        self._status_lock = threading.Lock()

        self._cmd_thread = threading.Thread(
            target=self._command_loop, daemon=True, name="servo-command",
        )
        self._status_thread = threading.Thread(
            target=self._status_loop, daemon=True, name="servo-status",
        )
        self._cmd_thread.start()
        self._status_thread.start()

    # -- producer API ------------------------------------------------------
    def _enqueue(self, batch):
        """Enqueue a batch of (path, params) commands, dropping the oldest."""
        try:
            self._queue.put_nowait(batch)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(batch)
            except queue.Full:
                pass

    def set_move(self, axis, direction):
        """Start continuous movement of ``axis`` in ``direction``.

        Coalesced: if the axis is already moving in that direction, nothing is
        enqueued. Otherwise the opposite direction is stopped first.
        """
        if axis not in self._desired:
            return
        with self._desired_lock:
            if self._desired[axis] == direction:
                return
            self._desired[axis] = direction
        dirs = _AXIS_STOP_DIRS[axis]
        opposite = dirs[0] if direction == dirs[1] else dirs[1]
        self._enqueue([
            ("/api/move", {"axis": axis, "dir": opposite, "cmd": "stop"}),
            ("/api/move", {"axis": axis, "dir": direction, "cmd": "start"}),
        ])

    def stop_axis(self, axis):
        """Stop continuous movement on ``axis`` (coalesced)."""
        if axis not in self._desired:
            return
        with self._desired_lock:
            if self._desired[axis] is None:
                return
            self._desired[axis] = None
        self._enqueue([
            ("/api/move", {"axis": axis, "dir": d, "cmd": "stop"})
            for d in _AXIS_STOP_DIRS[axis]
        ])

    def stop_all(self):
        """Stop continuous movement on both axes."""
        self.stop_axis("x")
        self.stop_axis("y")

    def trigger(self, state):
        """Fire or retract the physical trigger."""
        self._enqueue([("/api/servo/trigger", {"state": state})])

    def set_angle(self, axis, angle):
        """Move an axis to an absolute angle."""
        self._enqueue([(f"/api/servo/{axis}", {"angle": angle})])

    def wait_for_angle(self, axis, target, timeout, poll_interval=THERMAL_TRACK_SETTLE_POLL):
        """Block until the cached status reports ``axis`` at ``target``.

        Used after an absolute move so the caller can compare the hot pixel
        against the *new* turret position instead of a stale one. Returns True
        once the reported angle matches ``target``, or False if ``timeout``
        elapses first (e.g. the command was dropped or the ESP32 is slow).
        """
        deadline = time.monotonic() + timeout
        while True:
            status = self.get_status()
            if status is not None and status.get(axis) == target:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(poll_interval)

    def get_status(self):
        """Return the latest cached status dict, or None if never fetched."""
        with self._status_lock:
            return dict(self._status) if self._status is not None else None

    def _reassert_batch(self):
        """Build a batch that re-states the full desired movement state.

        Returns a list of (path, params) commands that drive every axis to its
        currently desired state: a moving axis gets its opposite direction
        stopped and its direction started, and a stopped axis gets both
        directions stopped. Re-sending the desired state makes the commands
        idempotent, so a previously dropped/ignored request is corrected and
        the ESP32 always knows which direction to move (or to stay stopped).
        """
        with self._desired_lock:
            desired = dict(self._desired)

        batch = []
        for axis, direction in desired.items():
            dirs = _AXIS_STOP_DIRS[axis]
            if direction is None:
                batch.extend(
                    ("/api/move", {"axis": axis, "dir": d, "cmd": "stop"})
                    for d in dirs
                )
                continue
            opposite = dirs[0] if direction == dirs[1] else dirs[1]
            batch.append(("/api/move", {"axis": axis, "dir": opposite, "cmd": "stop"}))
            batch.append(("/api/move", {"axis": axis, "dir": direction, "cmd": "start"}))
        return batch

    # -- worker loops ------------------------------------------------------
    def _command_loop(self):
        last_refresh = time.monotonic()
        while not self._stop.is_set():
            try:
                batch = self._queue.get(timeout=0.1)
            except queue.Empty:
                # Nothing queued: periodically re-assert the desired movement
                # so the ESP32 always knows which direction to move, even if an
                # earlier command was dropped or ignored.
                if time.monotonic() - last_refresh >= self._move_refresh_interval:
                    batch = self._reassert_batch()
                    last_refresh = time.monotonic()
                else:
                    continue
            for path, params in batch:
                if self._stop.is_set():
                    return
                servo_get(self._base_url, path, params, self._http_timeout)

    def _status_loop(self):
        while not self._stop.is_set():
            resp = servo_get(self._base_url, "/api/status", timeout=self._http_timeout)
            if resp is not None and resp.status_code == 200:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = None
                if payload is not None:
                    with self._status_lock:
                        self._status = payload
            self._stop.wait(self._status_poll_interval)

    def close(self):
        """Stop the worker threads."""
        self._stop.set()
        for thread in (self._cmd_thread, self._status_thread):
            if thread is not None:
                thread.join(timeout=1.0)
