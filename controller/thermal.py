"""AMG8833 thermal verification layer.

The AMG8833 (Panasonic Grid-EYE) thermal camera is wired to an Arduino Uno
over USB serial (VIN=5V, GND=GND, SCL=A5, SDA=A4). The Uno reads the 8x8 pixel
grid, finds the hottest pixel, and streams it over USB serial as:

    HOT,<temp_c>,<row>,<col>

This module wraps that serial stream in a background reader thread and exposes
the hottest pixel temperature plus a boolean "thermal OK" verdict used as a
second verification layer before the fire trigger fires.

The wire protocol and parsing logic mirror `amg8833_test.py` and the Arduino
sketch at `arduino/thermal/thermal.ino`.
"""

import sys
import threading
import time

# Prefix the Arduino sketch uses for hot-pixel lines. Any other line (boot
# banner, error text) is ignored.
HOT_PREFIX = "HOT,"

# If no fresh HOT line arrives within this many seconds, the sensor is treated
# as unavailable (stale). The Arduino streams at ~10 Hz, so 2 s is generous.
STALE_SECONDS = 2.0


def parse_hot_line(line):
    """Parse a 'HOT,<temp>,<row>,<col>' line.

    Returns (temp, row, col) as (float, int, int), or None if the line is not
    a valid hot-pixel line.
    """
    if not line.startswith(HOT_PREFIX):
        return None
    parts = line.split(",")
    if len(parts) != 4:
        return None
    try:
        temp = float(parts[1])
        row = int(parts[2])
        col = int(parts[3])
    except ValueError:
        return None
    return temp, row, col


def open_serial(port, baud):
    """Open the serial port, or raise RuntimeError with a helpful message."""
    try:
        import serial
    except ImportError as exc:
        raise RuntimeError(
            "pyserial is not installed. Run: pip install pyserial"
        ) from exc

    try:
        return serial.Serial(port=port, baudrate=baud, timeout=1)
    except serial.SerialException as exc:
        raise RuntimeError(
            f"Could not open serial port {port} at {baud} baud: {exc}. "
            "Check that the Arduino is connected and the port is correct "
            "(Arduino IDE > Tools > Port)."
        ) from exc


class ThermalSensor:
    """Reads the hottest AMG8833 pixel temperature from a serial bridge.

    Opens the serial port and runs a daemon reader thread that parses
    ``HOT,<temp>,<row>,<col>`` lines, keeping the latest temperature and its
    timestamp. ``read()`` returns the current max temperature and whether it
    clears the configured threshold.

    If the serial port cannot be opened, the sensor is marked unavailable and
    ``read()`` reports ``thermal_ok`` according to ``fail_open`` so the rest of
    the controller can still boot and run without the sensor attached.
    """

    def __init__(self, port, baud, threshold_c, fail_open=True):
        self._threshold_c = threshold_c
        self._fail_open = fail_open
        self._lock = threading.Lock()
        self._max_temp_c = None
        self._last_read_time = None
        self._available = False
        self._stop = threading.Event()
        self._thread = None
        self._ser = None

        try:
            self._ser = open_serial(port, baud)
        except RuntimeError as exc:
            print(f"Thermal sensor unavailable: {exc}")
            return

        self._available = True
        self._thread = threading.Thread(
            target=self._reader_loop,
            daemon=True,
            name="thermal-reader",
        )
        self._thread.start()

    @property
    def available(self):
        """True if the serial port was opened successfully."""
        return self._available

    def _reader_loop(self):
        """Read and parse HOT lines until stopped."""
        while not self._stop.is_set():
            try:
                raw = self._ser.readline()
            except Exception as exc:
                print(f"Thermal serial read error: {exc}")
                break
            if not raw:
                # Timeout with no data; keep waiting.
                continue
            line = raw.decode("ascii", errors="ignore").strip()
            if not line:
                continue

            parsed = parse_hot_line(line)
            if parsed is None:
                # Boot banner or error line from the Arduino; surface errors.
                if line.startswith("ERROR,"):
                    print(f"Arduino error: {line[len('ERROR,'):]}",
                          file=sys.stderr)
                continue

            temp, _row, _col = parsed
            now = time.monotonic()
            with self._lock:
                self._max_temp_c = temp
                self._last_read_time = now

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
        """Stop the reader thread and close the serial port."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
        self._available = False