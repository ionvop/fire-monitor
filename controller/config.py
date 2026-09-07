import os

# Load secrets/overrides from the gitignored .env file (VAPID keys, API base
# URL). Values in .env take precedence over the defaults below.
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

SERVO_IP = "192.168.4.1"
MIN_FIRE_DURATION = 1.0

# Debug safety switch: when True, the physical trigger is never fired, neither
# from automatic fire-on-detection nor from the manual dashboard trigger. Theq
# safe "retract" state still works. Set to False for normal operation.
DEBUG_DISABLE_TRIGGER = True

# Webcam
WEBCAM_INDEX = 0

# Fire detection
FIRE_CONF_THRESHOLD = 0.7

# Fire screenshot auto-capture
CAPTURE_DIR = "captures"          # directory (gitignored) for saved fire screenshots
CAPTURE_MAX = 50                  # keep at most this many captures (oldest removed)
CAPTURE_ENABLED_DEFAULT = True    # initial state of the auto-capture toggle

# Dashboard server
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# Automatic scanning (clockwise rectangle via /api/move)
SCAN_X_MIN = 10
SCAN_X_MAX = 170
SCAN_Y_MIN = 70
SCAN_Y_MAX = 110
SCAN_CORNER_TOLERANCE = 10  # degrees of error allowed before a corner is "reached"
SCAN_STATUS_POLL_INTERVAL = 0.1  # seconds between /api/status polls

# Fire is considered "centered" when its bbox center is within this many pixels
# of the frame center; the turret stops moving once inside this deadzone.
FIRE_TRACK_DEADBAND_PIXELS = 20

# ---------------------------------------------------------------------------
# Remote alerting (fire_history logging + Web Push notifications)
# ---------------------------------------------------------------------------
# Base URL of the deployed PWA API. Overridable via API_BASE_URL in .env.
API_BASE_URL = os.getenv("API_BASE_URL", "https://firemonitor.ionvop.com/api")

# Cooldown between fire alerts (seconds). While a cooldown is active, a new
# detection is neither logged to fire_history nor pushed to subscribers.
ALERT_COOLDOWN_SECONDS = 3600  # 1 hour

# Master switch for sending Web Push notifications. When False, detections are
# still logged to fire_history but no push is sent.
PUSH_ENABLED = os.getenv("PUSH_ENABLED", "true").lower() in ("1", "true", "yes")

# VAPID keys for Web Push (loaded from .env). The public key is embedded in the
# PWA bundle; the private key must stay server-side (here, on the controller).
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")

# Email/URL used as the VAPID "sub" claim when signing push requests.
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "admin@firemonitor.ionvop.com")