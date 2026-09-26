"""Real-time AMG8833 hot-pixel temperature test (Arduino Uno over serial).

The AMG8833 (Panasonic Grid-EYE) thermal camera is wired to an Arduino Uno
(VIN=5V, GND=GND, SCL=A5, SDA=A4). The Uno reads the 8x8 pixel grid, finds the
hottest pixel, and streams it over USB serial as:

    HOT,<temp_c>,<row>,<col>

This script opens that serial port, parses each line, and prints the
temperature of the hottest pixel in real time.

Usage:
    python amg8833_test.py                       # COM3 @ 115200
    python amg8833_test.py --port COM5           # different port
    python amg8833_test.py --port COM3 --baud 9600

Exits with an error if the serial port cannot be opened (wrong port, board not
connected, or pyserial not installed).
"""

import argparse
import sys

DEFAULT_PORT = "COM5"
DEFAULT_BAUD = 115200

# Prefix the Arduino sketch uses for hot-pixel lines. Any other line (boot
# banner, error text) is ignored.
HOT_PREFIX = "HOT,"


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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read the hottest pixel temperature of an AMG8833 via an "
        "Arduino Uno over serial."
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"Serial port of the Arduino (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"Serial baud rate (default: {DEFAULT_BAUD}).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    try:
        ser = open_serial(args.port, args.baud)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Reading AMG8833 hot-pixel temperature from {args.port} "
          f"at {args.baud} baud. Press Ctrl+C to stop.\n")
    try:
        while True:
            raw = ser.readline()
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

            temp, row, col = parsed
            print(f"Hottest pixel: {temp:.1f} C at (row={row}, col={col})")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        try:
            ser.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())