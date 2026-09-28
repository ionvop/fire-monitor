"""Real-time AMG8833 hot-pixel temperature test (ESP32 over HTTP).

The AMG8833 (Panasonic Grid-EYE) thermal camera is wired directly to the servo
ESP32 over I2C (VIN=3V3, GND=GND, SDA=GPIO21, SCL=GPIO22). The ESP32 reads the
8x8 pixel grid, finds the hottest pixel, and exposes it over its access-point
HTTP server as:

    GET http://<SERVO_IP>/api/thermal
    -> {"ok":true,"max_temp_c":<float>,"row":<int>,"col":<int>}

This script polls that endpoint and prints the temperature of the hottest pixel
in real time.

Usage:
    python amg8833_test.py                       # 192.168.4.1
    python amg8833_test.py --ip 192.168.4.1      # explicit ESP32 IP
    python amg8833_test.py --interval 0.5        # slower polling

Exits with an error if the endpoint cannot be reached (wrong IP, ESP32 not
powered, or not connected to the ESP32 access point).
"""

import argparse
import sys
import time

import requests

DEFAULT_IP = "192.168.4.1"
DEFAULT_INTERVAL = 0.2
DEFAULT_TIMEOUT = 1.0


def parse_thermal_response(payload):
    """Parse a /api/thermal JSON payload.

    Returns (temp, row, col) as (float, int, int), or None if the payload does
    not represent a valid reading.
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


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read the hottest pixel temperature of an AMG8833 via the "
        "servo ESP32 HTTP API."
    )
    parser.add_argument(
        "--ip",
        default=DEFAULT_IP,
        help=f"IP address of the servo ESP32 (default: {DEFAULT_IP}).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between polls (default: {DEFAULT_INTERVAL}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request HTTP timeout in seconds (default: {DEFAULT_TIMEOUT}).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    url = f"http://{args.ip}/api/thermal"

    print(f"Reading AMG8833 hot-pixel temperature from {url}. "
          "Press Ctrl+C to stop.\n")
    try:
        while True:
            try:
                resp = requests.get(url, timeout=args.timeout)
                payload = resp.json()
            except requests.RequestException as exc:
                print(f"Request failed: {exc}", file=sys.stderr)
                time.sleep(args.interval)
                continue
            except ValueError:
                print("Invalid JSON from ESP32.", file=sys.stderr)
                time.sleep(args.interval)
                continue

            parsed = parse_thermal_response(payload)
            if parsed is None:
                error = payload.get("error") if isinstance(payload, dict) else None
                print(f"ESP32 error: {error or 'invalid reading'}",
                      file=sys.stderr)
            else:
                temp, row, col = parsed
                print(f"Hottest pixel: {temp:.1f} C at (row={row}, col={col})")

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())