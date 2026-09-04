# Message for the `controller/` agent — Sending fire alerts via Firebase

> Relay this to the agent working on `../controller/` (the Python YOLO controller).

## Goal

The Flutter app (`app/`) is now wired to Firebase project **`fire-monitor-316a5`** and listens in real time to a Firestore collection named **`alerts`**. Your job is to make the controller **write a document to that collection every time it detects a fire**, so the app can display and log the alert — even when the user is away and on a different network.

You do **not** need to send push notifications or manage device tokens. The app already handles the real-time listening. You only need to **write documents to Firestore**.

## The contract (document schema)

Write each alert as a new document in the `alerts` collection with these fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `timestamp` | Firestore `Timestamp` | Yes | When the fire was detected. |
| `status` | `string` | Yes | `"detected"` when firing starts, `"retracted"` when it ends. |
| `confidence` | `number` | No | Detection confidence (0.0–1.0). |
| `x` | `number` | No | Servo pan angle at detection. |
| `y` | `number` | No | Servo tilt angle at detection. |
| `captureImageUrl` | `string` | No | URL of the annotated capture image, if one is saved. |

The app reads these exact field names, so keep them as-is. The app sorts by `timestamp` descending and shows the newest 50.

## Setup in the controller

1. **Add the dependency** to `controller/requirements.txt`:
   ```
   firebase-admin
   ```

2. **Get a service-account key** for project `fire-monitor-316a5`:
   - Firebase Console → Project `fire-monitor-316a5` → Project settings → Service accounts → **Generate new private key**.
   - Save the downloaded JSON (e.g. `controller/firebase-service-account.json`). **Do not commit it** — add it to `.gitignore`.

3. **Initialize the SDK** at controller startup (before the detection loop):
   ```python
   import firebase_admin
   from firebase_admin import credentials, firestore

   cred = credentials.Certificate("firebase-service-account.json")
   firebase_admin.initialize_app(cred)
   db = firestore.client()
   ```

## Where to write the alert

In `controller/main.py`, the detection loop already tracks fire state transitions. Hook in at the two points where the state changes:

- **On first detection** — where `fire_trigger()` is called and `fire_active` is set to `True` (this is also where `save_capture()` is called). Write a document with `status: "detected"`, the current `timestamp`, and any `confidence` / `x` / `y` / `captureImageUrl` you have:
  ```python
  db.collection("alerts").add({
      "timestamp": firestore.SERVER_TIMESTAMP,
      "status": "detected",
      "confidence": best_conf,          # if available
      "x": x_angle,                     # if available
      "y": y_angle,                     # if available
      "captureImageUrl": capture_url,   # if you upload the capture
  })
  ```

- **On retract** — where the trigger is retracted and `fire_active` is set to `False`. Write a follow-up document with `status: "retracted"` (same `timestamp`/angles) so the app can show the alert as resolved.

Use `firestore.SERVER_TIMESTAMP` (or a Python `datetime` in UTC) so the app's `timestamp` ordering works correctly.

## Notes

- **Firestore rules:** The app currently has no authentication, so the `alerts` collection must be readable by the app. If the rules are locked down, set them to allow read/write (test mode) for now, or add Firebase Auth later.
- **Capture images:** If you want the app to show the fire screenshot, upload the JPEG to Firebase Storage and store the download URL in `captureImageUrl`. (Storing raw image bytes directly in the Firestore document is not recommended — documents are limited to ~1 MB.)
- **Testing:** You can verify end-to-end by adding a document to the `alerts` collection from the Firebase Console while the app is running — it should appear in the app's list immediately.