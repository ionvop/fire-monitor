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
DEBUG_DISABLE_TRIGGER = False

# Webcam
WEBCAM_INDEX = 0

# Fire detection
# Webcam/YOLO confidence threshold. This only controls which detections are
# drawn on the dashboard preview; it no longer gates aiming or firing (the
# AMG8833 thermal sensor is the sole trigger).
FIRE_CONF_THRESHOLD = 0.7

# AMG8833 thermal camera
# The AMG8833 is wired directly to the servo ESP32 over I2C and exposed at
# http://<SERVO_IP>/api/thermal. It provides the hottest pixel's temperature
# AND its grid position (row/col). The thermal sensor is the sole trigger for
# aiming and firing: the hottest pixel must exceed THERMAL_THRESHOLD_C before
# the trigger fires. The row/col position drives turret aiming: the controller
# steers toward the hottest pixel rather than the webcam fire bbox.
THERMAL_ENABLED = True
THERMAL_THRESHOLD_C = 40.0
# How often the controller polls the ESP32 /api/thermal endpoint (seconds).
THERMAL_POLL_INTERVAL = 0.1
# Per-request HTTP timeout when polling the thermal endpoint (seconds).
THERMAL_HTTP_TIMEOUT = 4.0
# When the thermal sensor is unavailable (endpoint unreachable or no fresh
# reading), THERMAL_FAIL_OPEN=True lets detection proceed (fail-open); False
# blocks firing (fail-closed). Note: firing also requires a fresh reading
# (hottest pixel row/col), so an unavailable sensor never triggers firing even
# when fail-open is set.
THERMAL_FAIL_OPEN = False

# AMG8833 grid orientation. The sensor reports an 8x8 grid (row 0..7, col 0..7,
# row-major). By default row 0 is the top and col 0 is the left, so a hot pixel
# with col > 3.5 is to the right and row > 3.5 is below center. Flip these if
# the sensor is mounted rotated/mirrored so aiming still tracks the heat.
THERMAL_FLIP_X = False
THERMAL_FLIP_Y = False
# The turret is considered aimed at the hot pixel when its grid offset from the
# grid center (3.5) is within this many pixels; the axis stops nudging inside
# it. 0 means it keeps microadjusting until the hot pixel is exactly centered.
THERMAL_TRACK_DEADBAND_PIXELS = 0

# Absolute-position thermal centering. Instead of continuous left/right/up/down
# movement, the controller reads the current X/Y angle, compares it with the
# hottest pixel's offset from the grid center, and nudges each off-center axis
# by this many degrees using an absolute move (/api/servo/{axis}?angle=). It
# then waits for the reported angle to reach the target and repeats.
THERMAL_TRACK_STEP_DEGREES = 5
# After issuing an absolute move, wait up to this long (seconds) for the ESP32
# to report the new angle before comparing again. This prevents double-stepping
# on a stale status cache while bounding how long the detection loop can block.
THERMAL_TRACK_SETTLE_TIMEOUT = 0.5
# How often (seconds) to re-read the cached status while waiting for the angle
# to reach the target.
THERMAL_TRACK_SETTLE_POLL = 0.02

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

# ---------------------------------------------------------------------------
# Async worker tuning
# ---------------------------------------------------------------------------
# Per-request HTTP timeout for servo commands issued by the background worker.
SERVO_HTTP_TIMEOUT = 4.0
# Bounded queue sizes for the background workers. When a queue is full the
# oldest item is dropped so the detection loop never blocks on a slow backend.
SERVO_CMD_QUEUE_MAX = 64
# Movement commands are coalesced (only sent when the desired direction
# changes), so a single dropped/ignored HTTP request would leave the turret
# stuck. The command worker re-asserts the current desired movement state to
# the ESP32 at this interval (seconds) so it always knows which direction to
# move. Keep this well below the time it takes the turret to visibly drift.
SERVO_MOVE_REFRESH_INTERVAL = 0.1
ALERT_QUEUE_MAX = 16
CAPTURE_QUEUE_MAX = 8

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