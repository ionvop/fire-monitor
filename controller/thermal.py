"""AMG8833 thermal verification layer.

The AMG8833 (Panasonic Grid-EYE) thermal camera is wired directly to the servo
ESP32 over I2C (VIN=3V3, GND=GND, SDA=GPIO21, SCL=GPIO22). The ESP32 reads the
8x8 pixel grid, finds the hottest pixel, and exposes it over its access-point
HTTP server as:

    GET http://<SERVO_IP>/api/thermal
    -> {"ok":true,"max_temp_c":<float>,"row":<int>,"col":<int>}

This module polls that endpoint in a background thread and exposes the hottest
pixel temperature plus a boolean "thermal OK" verdict used as a second
verification layer before the fire trigger fires.

The wire protocol mirrors the ESP32 sketch at `arduino/servo/servo.ino`.
"""

import threading
import time

import requests

# If no fresh reading arrives within this many seconds, the sensor is treated
# as unavailable (stale). The controller polls at THERMAL_POLL_INTERVAL, so a
# few seconds is generous.
STALE_SECONDS = 2.0


def parse_thermal_response(payload):
    """Parse a /api/thermal JSON payload.

    Returns (temp, row, col) as (float, int, int), or None if the payload does
    not represent a valid reading (ok is false, missing fields, bad types).
    """
    if not isinstance(payload, dict) or not payload.get("ok"):
        return None
    try:
        temp = float(payload["max_temp_c"])
        row = int(payload["row"])
        col = int(payload["col"])
    except (KeyError, TypeError, ValueError):
        return None
    return temp, row, col


class ThermalSensor:
    """Reads the hottest AMG8833 pixel temperature from the ESP32 HTTP API.

    Runs a daemon poller thread that GETs ``/api/thermal`` on the servo ESP32,
    keeping the latest temperature and its timestamp. ``read()`` returns the
    current max temperature and whether it clears the configured threshold.

    If the endpoint is unreachable, the sensor is marked unavailable and
    ``read()`` reports ``thermal_ok`` according to ``fail_open`` so the rest of
    the controller can still boot and run without the sensor attached.
    """

    def __init__(self, base_url, threshold_c, poll_interval=0.2,
                 http_timeout=1.0, fail_open=True):
        self._url = f"{base_url.rstrip('/')}/api/thermal"
        self._threshold_c = threshold_c
        self._poll_interval = poll_interval
        self._http_timeout = http_timeout
        self._fail_open = fail_open
        self._lock = threading.Lock()
        self._max_temp_c = None
        self._last_read_time = None
        self._available = False
        self._stop = threading.Event()
        self._thread = None

        # Probe once so `available` reflects reality at construction time.
        self._available = self._poll_once()

        self._thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
            name="thermal-reader",
        )
        self._thread.start()

    @property
    def available(self):
        """True if the ESP32 thermal endpoint responded successfully."""
        return self._available

    def _poll_once(self):
        """Fetch and parse one reading. Returns True on a valid reading."""
        try:
            resp = requests.get(self._url, timeout=self._http_timeout)
        except requests.RequestException:
            return False
        if resp.status_code != 200:
            return False
        try:
            payload = resp.json()
        except ValueError:
            return False

        parsed = parse_thermal_response(payload)
        if parsed is None:
            return False

        temp, _row, _col = parsed
        with self._lock:
            self._max_temp_c = temp
            self._last_read_time = time.monotonic()
        return True

    def _reader_loop(self):
        """Poll the ESP32 endpoint until stopped."""
        while not self._stop.is_set():
            self._available = self._poll_once()
            self._stop.wait(self._poll_interval)

    def read(self):
        """Return (max_temp_c, thermal_ok).

        ``max_temp_c`` is the hottest pixel temperature in degrees Celsius, or
        None if the sensor is unavailable or stale. ``thermal_ok`` is True when
        the temperature clears the threshold; when the sensor is unavailable or
        stale it follows the ``fail_open`` setting.
        """
        with self._lock:
            max_temp_c = self._max_temp_c
            last_read_time = self._last_read_time

        if not self._available or max_temp_c is None:
            return None, self._fail_open

        if last_read_time is not None and (
            time.monotonic() - last_read_time > STALE_SECONDS
        ):
            return None, self._fail_open

        return max_temp_c, max_temp_c >= self._threshold_c

    def close(self):
        """Stop the poller thread."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._available = False