SERVO_IP = "192.168.4.1"
<<<<<<< Updated upstream
=======
<<<<<<< Updated upstream
CAMERA_IP = "192.168.4.2"
MIN_FIRE_DURATION = 1.0
=======
>>>>>>> Stashed changes
MIN_FIRE_DURATION = 1.0

# Webcam
WEBCAM_INDEX = 1

# Fire detection
<<<<<<< Updated upstream
FIRE_CONF_THRESHOLD = 0.5
=======
FIRE_CONF_THRESHOLD = 0.76
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
SCAN_Y_MAX = 110
SCAN_CORNER_TOLERANCE = 10  # degrees of error allowed before a corner is "reached"
SCAN_STATUS_POLL_INTERVAL = 0.1  # seconds between /api/status polls
=======
SCAN_Y_MAX = 180
SCAN_CORNER_TOLERANCE = 10  # degrees of error allowed before a corner is "reached"
SCAN_STATUS_POLL_INTERVAL = 0.1  # seconds between /api/status polls
>>>>>>> Stashed changes
>>>>>>> Stashed changes
