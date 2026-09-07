"""Standalone test script: force-send a fire detection alert.

Sends a fire detection to the remote backend (logs to fire_history and pushes
to all subscribed PWA users), bypassing the 1-hour cooldown so it always fires.

Usage:
    python send_test_alert.py            # force-send a detection alert
    python send_test_alert.py --retract  # send a retraction instead
"""

import argparse

from alerts import report_fire


def main() -> None:
    parser = argparse.ArgumentParser(description="Force-send a fire alert for testing.")
    parser.add_argument(
        "--retract",
        action="store_true",
        help="Send a retraction instead of a detection.",
    )
    parser.add_argument("--confidence", type=float, default=0.99,
                        help="Confidence score to report (default: 0.99).")
    parser.add_argument("--x", type=float, default=90.0,
                        help="Servo pan angle (default: 90).")
    parser.add_argument("--y", type=float, default=90.0,
                        help="Servo tilt angle (default: 90).")
    args = parser.parse_args()

    status = "retracted" if args.retract else "detected"
    print(f"Sending {status} alert (force, bypassing cooldown)...")
    report_fire(
        status,
        args.confidence,
        args.x,
        args.y,
        force=True,
    )
    print("Done.")


if __name__ == "__main__":
    main()