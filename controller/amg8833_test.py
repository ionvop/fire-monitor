"""Real-time AMG8833 thermal camera hot-pixel temperature test.

Reads the 8x8 pixel temperature grid from an AMG8833 (Panasonic Grid-EYE)
thermal camera over I2C and reports the temperature of the hottest pixel in
real time.

On Windows (or any machine without an I2C bus / smbus2), the script falls back
to a built-in simulator so the output format and hot-pixel detection can be
tested without hardware.

Usage:
    python amg8833_test.py                 # real hardware (Linux/Raspberry Pi)
    python amg8833_test.py --simulate      # force the simulator
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


class SimulatedAMG8833:
    """Synthetic AMG8833 for testing without hardware.

    Produces an 8x8 grid with a warm background and a hot spot that drifts
    around the grid so hot-pixel detection can be verified in real time.
    """

    def __init__(self):
        self._t = 0.0

    def read_grid(self):
        self._t += 0.25
        # Warm background (~24 C) with a little noise.
        rng = np.random.default_rng()
        grid = 24.0 + rng.normal(0.0, 0.3, (GRID_SIZE, GRID_SIZE))
        # Hot spot orbiting the grid.
        cx = 3.5 + 3.0 * np.cos(self._t)
        cy = 3.5 + 3.0 * np.sin(self._t)
        rows, cols = np.mgrid[0:GRID_SIZE, 0:GRID_SIZE]
        dist = np.sqrt((rows - cy) ** 2 + (cols - cx) ** 2)
        grid += 45.0 * np.exp(-(dist ** 2) / 2.0)
        return grid.astype(np.float32)

    def close(self):
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
    """Return a working sensor, preferring real hardware unless forced off."""
    if args.simulate:
        print("Using SIMULATOR (--simulate).")
        return SimulatedAMG8833()

    try:
        sensor = AMG8833(bus_number=args.i2c_bus)
        print(f"Using real AMG8833 on I2C bus {args.i2c_bus}.")
        return sensor
    except Exception as exc:
        print(
            f"Could not open AMG8833 on I2C bus {args.i2c_bus} ({exc}).\n"
            "Falling back to the built-in simulator. "
            "On Windows there is no native I2C bus; run on a Raspberry Pi "
            "with smbus2 installed for real readings."
        )
        return SimulatedAMG8833()


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
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Force the simulator instead of real hardware.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    sensor = build_sensor(args)

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