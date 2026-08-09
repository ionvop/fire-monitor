# fire-monitor

This project is an **AI-powered Fire Extinguishing Turret system**. It uses a **webcam** for vision, an **ESP32** to control pan/tilt servos and a firing mechanism, and a **Python-based YOLO (You Only Look Once) controller** that automates fire detection, room scanning, and engagement. The controller also serves a web dashboard for manual control.

---

## 🏗️ System Architecture

The project is divided into three main components:

1. **Arduino (Firmware):**
    * **Servo:** An ESP32 that controls two servos (Pan/Tilt) and two digital pins for a firing/retracting mechanism. It runs a web server to receive movement and firing commands.

2. **Controller (AI Brain):** A Python script running YOLOv8. It captures video from a **webcam**, detects fire, scans the room by driving the servo's movement endpoints, and sends logic commands to the Servo controller. It also serves the dashboard and proxies manual-control commands.

3. **Dashboard (Manual Control):** A web-based interface served by the controller to view the live (annotated) stream and manually control the turret's movement and firing. When a user is connected, the controller pauses automatic scanning.

---

## 📂 Project Structure

```text
├── arduino/
│   └── servo/              # Servo & Firing mechanism firmware
├── controller/
│   ├── main.py             # YOLOv8 detection, scanning, & dashboard server
│   ├── config.py           # IP & behavior configuration
│   ├── requirements.txt    # Python dependencies
│   └── best.pt             # YOLO model weights (fire detection)
└── dashboard/
    └── index.html          # Web UI (served by the controller)
```

---

## 🚀 Getting Started

### 1. Hardware Setup

* **Camera:** A USB webcam connected to the computer running the controller.
* **Servo Controller:** ESP32.
* **Servos:** 2x Servos connected to Pins 12 (Y) and 13 (X).
* **Trigger:** Relays or MOSFETs connected to Pins 26 (Fire) and 27 (Retract).

### 2. Firmware Installation (Arduino)

1. Navigate to the `arduino/` folder.
2. Open `arduino/servo/servo.ino`, select your ESP32 board, and upload.
* *Note:* You will need the `ESP32Servo` library installed in your Arduino IDE.

### 3. AI Controller Setup (Python)

1. Navigate to the `controller/` folder.
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Edit `config.py` and set the IP address of your Servo ESP32 (`SERVO_IP`).
4. Place your YOLO model weights file as `best.pt` in the `controller/` directory.
5. Run the controller:
```bash
python main.py
```

### 4. Dashboard

1. With the controller running, open `http://localhost:5000` in any modern web browser.
2. The dashboard shows the live annotated webcam stream and lets you control the turret manually.
3. While the dashboard is open, automatic scanning is paused so you can take manual control. Closing the dashboard resumes automatic scanning.

---

## 🛠️ Configuration

All behavior is configured in `controller/config.py`:

| Setting | Default | Description |
| --- | --- | --- |
| `SERVO_IP` | `192.168.4.1` | IP address of the Servo ESP32. |
| `MIN_FIRE_DURATION` | `1.0` | Seconds the trigger stays in the `fire` state before retracting. |
| `WEBCAM_INDEX` | `0` | Index of the webcam used for video capture. |
| `FIRE_CONF_THRESHOLD` | `0.5` | Minimum confidence for a detection to count as fire. |
| `DASHBOARD_HOST` | `0.0.0.0` | Host the dashboard server binds to. |
| `DASHBOARD_PORT` | `5000` | Port the dashboard server listens on. |
| `SCAN_X_MIN` / `SCAN_X_MAX` | `0` / `180` | Pan (X) sweep limits in degrees. |
| `SCAN_Y_MIN` / `SCAN_Y_MAX` | `0` / `180` | Tilt (Y) sweep limits in degrees. |
| `SCAN_Y_STEP` | `10` | Tilt step size between sweep rows. |
| `SCAN_STATUS_POLL_INTERVAL` | `0.1` | Seconds between `/api/status` polls during scanning. |
| `SCAN_Y_STEP_INTERVAL` | `3.0` | Seconds between tilt steps during scanning. |

---

## 🔌 API

### Controller API (served by `main.py`)

The controller exposes the dashboard and proxies commands to the Servo ESP32:

| Endpoint | Method | Description |
| --- | --- | --- |
| `/` | GET | Serves the dashboard HTML. |
| `/video_feed` | GET | MJPEG stream of the annotated webcam feed. |
| `/api/status` | GET | Servo angles plus `manual_mode` and `fire_active` flags. |
| `/api/move` | GET | Proxy for servo movement (`axis`, `dir`, `cmd`). |
| `/api/servo/trigger` | GET | Proxy for firing (`state=fire` / `state=retract`). |
| `/api/servo/x` | GET | Proxy to set the X angle (`angle`). |
| `/api/servo/y` | GET | Proxy to set the Y angle (`angle`). |

### Servo HTTP Endpoints (ESP32)

The Servo ESP32 exposes the following endpoints for integration:

| Endpoint | Parameters | Description |
| --- | --- | --- |
| `/api/status` | — | Returns current `x`, `y`, and `trigger` angles as JSON. |
| `/api/move` | `axis=x/y`, `dir=left/right/up/down`, `cmd=start/stop` | Continuous movement control. |
| `/api/servo/trigger` | `state=fire/retract` | Activates `fire()` or `retract()`. |
| `/api/servo/x` | `angle=0-180` | Sets the X (pan) angle. |
| `/api/servo/y` | `angle=0-180` | Sets the Y (tilt) angle. |

---

## 🧠 Behavior

* **Detection:** The controller runs the YOLO model on each webcam frame. A detection of **Class 0** (fire) with confidence above `FIRE_CONF_THRESHOLD` triggers engagement.
* **Scanning:** When no user is connected and no fire is active, the controller sweeps the turret across the room using the `/api/move` endpoints, reversing at the configured sweep limits and stepping the tilt axis periodically.
* **Engagement:** On fire detection, the controller stops scanning and sends `trigger?state=fire`. After `MIN_FIRE_DURATION` seconds it sends `trigger?state=retract`, then resumes scanning.
* **Manual mode:** When a dashboard user connects (via WebSocket), the controller stops automatic scanning and lets the user control the turret manually. When the last user disconnects, automatic scanning resumes.

---

### Disclaimer

This documentation was generated by Gemini but the entire codebase was written by hand.