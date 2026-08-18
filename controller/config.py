SERVO_IP = "192.168.4.1"
MIN_FIRE_DURATION = 1.0

# Webcam
WEBCAM_INDEX = 1

# Fire detection
FIRE_CONF_THRESHOLD = 0.5

# Dashboard server
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000

# Automatic scanning (continuous sweep via /api/move)
SCAN_X_MIN = 0
SCAN_X_MAX = 180
SCAN_Y_MIN = 0
SCAN_Y_MAX = 180
SCAN_Y_STEP = 10
SCAN_STATUS_POLL_INTERVAL = 0.1  # seconds between /api/status polls
SCAN_Y_STEP_INTERVAL = 3.0       # seconds between Y steps