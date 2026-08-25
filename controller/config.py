SERVO_IP = "192.168.4.1"
MIN_FIRE_DURATION = 1.0

# Debug safety switch: when True, the physical trigger is never fired, neither
# from automatic fire-on-detection nor from the manual dashboard trigger. The
# safe "retract" state still works. Set to False for normal operation.
DEBUG_DISABLE_TRIGGER = True

# Webcam
WEBCAM_INDEX = 1

# Fire detection
FIRE_CONF_THRESHOLD = 0.5

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