"""Real-time AMG8833 thermal camera hot-pixel temperature test.

Reads the 8x8 pixel temperature grid from an AMG8833 (Panasonic Grid-EYE)
thermal camera over I2C and reports the temperature of the hottest pixel in
real time.

Exits with an error if no AMG8833 hardware is detected (no I2C bus, no
smbus2, or no device at the expected address).

Usage:
    python amg8833_test.py                 # real hardware (Linux/Raspberry Pi)
    python amg8833_test.py --interval 0.5  # update every 0.5 s
"""

import argparse
import sys
import time

import numpy as np

# AMG8833 register map (datasheet).
AMG8833_I2C_ADDR = 0x69
AMG8833_TEMP_REG = 0x80  # first of 64 consecutive 16-bit temperature registers
GRID_SIZE = 8            # 8x8 pixels


class AMG8833:
    """Reads the 8x8 temperature grid from a real AMG8833 over I2C."""

    def __init__(self, bus_number=1, address=AMG8833_I2C_ADDR):
        import smbus2

        self._bus = smbus2.SMBus(bus_number)
        self._address = address

    def read_grid(self):
        """Return an 8x8 numpy array of temperatures in degrees Celsius."""
        # Read all 64 temperature registers (128 bytes) in one transaction.
        raw = self._bus.read_i2c_block_data(
            self._address, AMG8833_TEMP_REG, GRID_SIZE * 2
        )
        grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=np.float32)
        for i in range(GRID_SIZE * GRID_SIZE):
            lo = raw[i * 2]
            hi = raw[i * 2 + 1]
            value = (hi << 8) | lo
            # 12-bit signed value in 0.25 C steps.
            if value & 0x0800:
                value -= 0x1000
            grid[i // GRID_SIZE, i % GRID_SIZE] = value * 0.25
        return grid

    def close(self):
        try:
            self._bus.close()
        except Exception:
            pass


def find_hottest_pixel(grid):
    """Return (max_temp, row, col) of the hottest pixel in the grid."""
    flat_index = int(np.argmax(grid))
    row, col = divmod(flat_index, GRID_SIZE)
    return float(grid[row, col]), row, col


def print_grid(grid, hot_row, hot_col):
    """Print the 8x8 grid, marking the hottest pixel with an asterisk."""
    print("   " + " ".join(f"{c:>5}" for c in range(GRID_SIZE)))
    for r in range(GRID_SIZE):
        cells = []
        for c in range(GRID_SIZE):
            marker = "*" if (r == hot_row and c == hot_col) else " "
            cells.append(f"{grid[r, c]:5.1f}{marker}")
        print(f"{r}  " + " ".join(cells))


def build_sensor(args):
    """Return a working AMG8833 sensor, or raise if no hardware is found."""
    try:
        sensor = AMG8833(bus_number=args.i2c_bus)
    except Exception as exc:
        raise RuntimeError(
            f"No AMG8833 hardware detected on I2C bus {args.i2c_bus}: {exc}. "
            "Check that the sensor is wired to I2C and that smbus2 is installed."
        ) from exc
    print(f"Using real AMG8833 on I2C bus {args.i2c_bus}.")
    return sensor


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Read the hottest pixel temperature of an AMG8833 in real time."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between reads (default: 1.0).",
    )
    parser.add_argument(
        "--i2c-bus",
        type=int,
        default=1,
        help="I2C bus number (default: 1, typical on Raspberry Pi).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        sensor = build_sensor(args)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("Reading AMG8833 hot-pixel temperature. Press Ctrl+C to stop.\n")
    try:
        while True:
            grid = sensor.read_grid()
            max_temp, row, col = find_hottest_pixel(grid)
            print(f"Hottest pixel: {max_temp:.1f} C at (row={row}, col={col})")
            print_grid(grid, row, col)
            print()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sensor.close()


if __name__ == "__main__":
    sys.exit(main())