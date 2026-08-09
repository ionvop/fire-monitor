Please rewrite the entire Python code so that it does the following:

1. Use the webcam for video capture. (We're scrapping the idea of using ESP32-CAM)
2. Use the `best.py` model for fire detection.
3. Using the movement endpoints in the Servo controller, scan the room for fire.
4. If fire is detected, send a `fire` command to the Servo controller.
5. This script also serves a dashboard for manual control.
6. If a user is connected to the dashboard, this script stops the automatic movement of the turret and allows manual control.