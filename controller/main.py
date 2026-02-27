from config import CAMERA_IP, SERVO_IP, MIN_FIRE_DURATION
from ultralytics import YOLO
import requests
import time
import cv2


def main():
    model = YOLO("best.pt")
    cap = cv2.VideoCapture(f"http://{CAMERA_IP}:81/stream")
    requests.get(f"http://{SERVO_IP}/surveillance?cmd=start")

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    print("Press ESC to exit...")
    last_state = None
    fire_start_time = None

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Failed to grab frame")
            break

        results = model(frame, imgsz=640)
        annotated_frame = results[0].plot()
        cv2.imshow("YOLOv8 Webcam", annotated_frame)
        fire_detected = False
        h, w, _ = frame.shape
        center_x, center_y = w // 2, h // 2
        tolerance_x = int(w * 0.5)
        tolerance_y = int(h * 0.5)
        boxes = results[0].boxes

        if boxes is not None:
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])

                if cls == 0 and conf > 0.5:
                    x1, y1, x2, y2 = box.xyxy[0]
                    box_center_x = int((x1 + x2) / 2)
                    box_center_y = int((y1 + y2) / 2)

                    if (abs(box_center_x - center_x) < tolerance_x and
                        abs(box_center_y - center_y) < tolerance_y):
                        fire_detected = True
                        break

        current_time = time.monotonic()

        if fire_detected:
            if last_state != "fire":
                requests.get(f"http://{SERVO_IP}/trigger?cmd=fire")
                fire_start_time = current_time
                last_state = "fire"
        else:
            if last_state == "fire":
                if fire_start_time is not None and (current_time - fire_start_time) >= MIN_FIRE_DURATION:
                    requests.get(f"http://{SERVO_IP}/trigger?cmd=retract")
                    last_state = "retract"
                    fire_start_time = None
            elif last_state != "retract":
                requests.get(f"http://{SERVO_IP}/trigger?cmd=retract")
                last_state = "retract"

        if cv2.waitKey(1) == 27:
            requests.get(f"http://{SERVO_IP}/trigger?cmd=retract")
            requests.get(f"http://{SERVO_IP}/surveillance?cmd=stop")
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()