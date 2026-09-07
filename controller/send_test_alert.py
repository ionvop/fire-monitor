"""Send a test fire alert to Firebase Firestore.

Standalone test script that writes a document to the `alerts` collection,
mirroring exactly what the controller's detection loop does in main.py, so you
can verify the Flutter app receives the alert end-to-end.

Usage:
    python send_test_alert.py            # send a "detected" alert
    python send_test_alert.py --retract  # send a "retracted" alert
    python send_test_alert.py --confidence 0.92 --x 120 --y 80

Only requires `firebase-admin` (already in requirements.txt). No Flask, cv2,
or ultralytics imports, so it runs standalone.
"""

import argparse
import os

import firebase_admin
from firebase_admin import credentials, firestore

# Same service-account key used by main.py. Keep the filename in sync if it
# ever changes.
SERVICE_ACCOUNT_KEY = "fire-monitor-316a5-firebase-adminsdk-fbsvc-097e88fe31.json"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send a test fire alert to the Firebase `alerts` collection."
    )
    parser.add_argument(
        "--retract",
        action="store_true",
        help="Send a 'retracted' alert instead of the default 'detected'.",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Detection confidence to include (0.0-1.0). Default: 0.95.",
    )
    parser.add_argument(
        "--x",
        type=float,
        default=90.0,
        help="Servo pan angle to include. Default: 90.0.",
    )
    parser.add_argument(
        "--y",
        type=float,
        default=90.0,
        help="Servo tilt angle to include. Default: 90.0.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(SERVICE_ACCOUNT_KEY):
        print(
            f"Service-account key not found ({SERVICE_ACCOUNT_KEY}); "
            "cannot send alert."
        )
        return 1

    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
    except Exception as exc:
        print(f"Firebase initialization failed: {exc}")
        return 1

    status = "retracted" if args.retract else "detected"
    doc = {
        "timestamp": firestore.SERVER_TIMESTAMP,
        "status": status,
        "confidence": args.confidence,
        "x": args.x,
        "y": args.y,
    }

    try:
        ref = db.collection("alerts").add(doc)
        print(f"Test alert sent: status={status} document_id={ref[1].id}")
        return 0
    except Exception as exc:
        print(f"Failed to send test alert ({status}): {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())