"""Remote fire alerting for the Fire Monitor controller.

This module is the integration point between the local detection loop and the
deployed PWA backend at ``API_BASE_URL`` (default
``https://firemonitor.ionvop.com/api``).

Two responsibilities:

1. **Logging** — POST fire detections/retractions to ``/api/fire_history/`` so
   the PWA can render the fire report list.
2. **Push notifications** — fetch the PWA's Web Push subscriptions from
   ``/api/subscriptions/`` and send each subscriber a push notification using
   the VAPID keys from ``.env``.

A 1-hour cooldown (``ALERT_COOLDOWN_SECONDS``) gates *both* logging and push:
while a cooldown is active, a new detection is a no-op. Retractions are always
logged (they are cheap and informative) but never pushed.

All network failures are non-fatal — the detection loop must keep running even
if the remote API is unreachable.
"""

import threading
import time

import requests

from config import (
    ALERT_COOLDOWN_SECONDS,
    API_BASE_URL,
    PUSH_ENABLED,
    VAPID_CLAIMS_EMAIL,
    VAPID_PRIVATE_KEY,
)

# In-memory cooldown state. Not persisted: a controller restart resets it.
_state_lock = threading.Lock()
_last_alert_ts = 0.0  # time.monotonic() of the last logged/pushed detection


def _now() -> float:
    return time.monotonic()


def _in_cooldown() -> bool:
    """Return True if a fire alert was sent within the cooldown window."""
    with _state_lock:
        return (_now() - _last_alert_ts) < ALERT_COOLDOWN_SECONDS


def _mark_alerted() -> None:
    global _last_alert_ts
    with _state_lock:
        _last_alert_ts = _now()


def _log_fire(status: str, confidence: float, x: float, y: float,
              capture_url: str | None) -> None:
    """POST a record to /api/fire_history/. Non-fatal on failure."""
    try:
        resp = requests.post(
            f"{API_BASE_URL}/fire_history/",
            json={
                "status": status,
                "confidence_score": confidence,
                "x": x,
                "y": y,
                "capture_image_url": capture_url,
                # "timestamp" is optional; the server defaults to UTC now.
            },
            timeout=5,
        )
        if resp.status_code >= 400:
            print(f"fire_history log failed ({resp.status_code}): {resp.text}")
    except requests.RequestException as exc:
        print(f"fire_history log failed: {exc}")


def _fetch_subscriptions() -> list:
    """Return the list of push subscriptions, or [] on failure."""
    try:
        resp = requests.get(f"{API_BASE_URL}/subscriptions/", timeout=5)
        if resp.status_code != 200:
            print(f"fetch subscriptions failed ({resp.status_code}): {resp.text}")
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError) as exc:
        print(f"fetch subscriptions failed: {exc}")
        return []


def send_push(title: str, body: str, data: dict | None = None) -> None:
    """Send a Web Push notification to every subscribed PWA user.

    Uses the VAPID private key from ``.env`` to sign the request. Non-fatal on
    failure; a dead subscription (HTTP 410 Gone) is logged and skipped.
    """
    if not PUSH_ENABLED:
        print("PUSH_ENABLED is False; skipping push notification.")
        return
    if not VAPID_PRIVATE_KEY:
        print("VAPID_PRIVATE_KEY is not set; skipping push notification.")
        return

    try:
        from pywebpush import WebPushException, WebPusher
    except ImportError:
        print("pywebpush is not installed; skipping push notification.")
        return

    payload = {"title": title, "body": body}
    if data:
        payload["data"] = data

    subscriptions = _fetch_subscriptions()
    if not subscriptions:
        print("No push subscriptions to notify.")
        return

    for sub in subscriptions:
        endpoint = sub.get("endpoint")
        subscription_info = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": sub.get("p256dh"),
                "auth": sub.get("auth"),
            },
        }
        try:
            WebPusher(subscription_info).send(
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
            )
            print(f"Push sent to {endpoint}")
        except WebPushException as exc:
            # 410 Gone means the subscription is stale; log and move on.
            print(f"Push failed for {endpoint}: {exc}")


def report_fire(status: str, confidence: float, x: float, y: float,
                capture_url: str | None = None, force: bool = False) -> None:
    """Report a fire detection/retraction to the remote backend.

    Args:
        status: "detected" or "retracted".
        confidence: YOLO confidence (0.0-1.0) at detection.
        x, y: servo pan/tilt angles at detection.
        capture_url: optional URL of the annotated capture image.
        force: bypass the cooldown (used by the standalone test script).

    On a fresh detection (not in cooldown), logs to fire_history and sends a
    push. Retractions are always logged but never pushed. All failures are
    non-fatal.
    """
    if status == "detected":
        if not force and _in_cooldown():
            print("Fire alert suppressed: cooldown active.")
            return
        _mark_alerted()

    _log_fire(status, confidence, x, y, capture_url)

    if status == "detected":
        send_push(
            "Fire detected",
            f"A fire was detected with {confidence:.0%} confidence.",
            data={"confidence": confidence, "x": x, "y": y},
        )