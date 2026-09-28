#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <Wire.h>
#include <Adafruit_AMG88xx.h>

const char* apSSID = "ESP32-Turret";
const char* apPassword = "12345678";
const int SERVO_X_PIN = 13;
const int SERVO_Y_PIN = 12;
const int MOVE_INTERVAL = 20; // ms between movement steps
const int RETRACT_PIN = 27;
const int FIRE_PIN = 26;
const int TRIGGER_PIN = 14;

// AMG8833 thermal camera on the ESP32's default I2C bus.
// Wiring (AMG8833 breakout -> ESP32):
//   VIN -> 3V3   (the AMG8833 is a 3.3V part; do NOT use 5V)
//   GND -> GND
//   SDA -> GPIO21
//   SCL -> GPIO22
//   INT -> not connected
const int I2C_SDA_PIN = 21;
const int I2C_SCL_PIN = 22;

Servo servoX;
Servo servoY;
Servo servoTrigger;

Adafruit_AMG88xx amg;
bool thermalReady = false;
// 8x8 = 64 pixels, stored row-major (index = row * 8 + col).
float thermalPixels[AMG88xx_PIXEL_ARRAY_SIZE];

// The X servo is physically wired inverted: servo angle 0 points right and
// 180 points left. The API and internal angleX always use the convention
// "higher = right, lower = left", so we flip the value only when writing to
// the servo hardware.
int apiToServoX(int api) {
  return 180 - api;
}

bool moveUp = false;
bool moveDown = false;
bool moveLeft = false;
bool moveRight = false;
int angleX = 90;
int angleY = 90;
int angleTrigger = 90;
unsigned long lastMoveTime = 0;
WebServer server(80);

void setup() {
  Serial.begin(115200);

  // Bring up the AMG8833 on the ESP32 I2C bus. If it is not detected, the
  // turret still runs; /api/thermal reports ok:false so the controller can
  // apply its fail-open/fail-closed policy.
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  thermalReady = amg.begin();
  if (thermalReady) {
    Serial.println("AMG8833 initialized.");
  } else {
    Serial.println("ERROR,AMG8833 not detected. Check wiring (VIN=3V3, GND=GND, SDA=GPIO21, SCL=GPIO22).");
  }

  servoX.attach(SERVO_X_PIN);
  servoY.attach(SERVO_Y_PIN);
  servoTrigger.attach(TRIGGER_PIN);
  servoX.write(90);
  servoY.write(90);
  servoTrigger.write(90);
  Serial.println("Starting Access Point...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID, apPassword);
  IPAddress IP = WiFi.softAPIP();
  Serial.println("Access Point Started!");
  Serial.print("SSID: ");
  Serial.println(apSSID);
  Serial.print("IP Address: ");
  Serial.println(IP);

  server.on("/", HTTP_GET, handleStatus);
  server.on("/api/status", HTTP_GET, handleStatus);
  server.on("/api/thermal", HTTP_GET, handleThermal);
  server.on("/api/servo/x", HTTP_GET, handleServoX);
  server.on("/api/servo/y", HTTP_GET, handleServoY);
  server.on("/api/servo/trigger", HTTP_GET, handleTrigger);
  server.on("/api/move", HTTP_GET, handleMove);
  server.begin();
  Serial.println("HTTP Server started.");
  pinMode(RETRACT_PIN, OUTPUT);
  pinMode(FIRE_PIN, OUTPUT);
  retract();
}

void loop() {
  server.handleClient();
  unsigned long now = millis();

  if (now - lastMoveTime >= MOVE_INTERVAL) {
    lastMoveTime = now;

    if (moveUp) {
      angleY += 1;

      if (angleY > 180) {
        angleY = 180;
      }
    }

    if (moveDown) {
      angleY -= 1;

      if (angleY < 0) {
        angleY = 0;
      }
    }

    if (moveLeft) {
      angleX -= 1;

      if (angleX < 0) {
        angleX = 0;
      }
    }

    if (moveRight) {
      angleX += 1;

      if (angleX > 180) {
        angleX = 180;
      }
    }

    servoX.write(apiToServoX(angleX));
    servoY.write(angleY);
    servoTrigger.write(angleTrigger);
    Serial.print("X: ");
    Serial.print(angleX);
    Serial.print(" Y: ");
    Serial.println(angleY);
  }
}

void handleStatus() {
  String json = "{";
  json += "\"x\":" + String(angleX) + ",";
  json += "\"y\":" + String(angleY) + ",";
  json += "\"trigger\":" + String(angleTrigger);
  json += "}";
  server.send(200, "application/json", json);
}

// GET /api/thermal
// Reads the 8x8 AMG8833 grid, finds the hottest pixel, and returns:
//   {"ok":true,"max_temp_c":<float>,"row":<int>,"col":<int>}
// or, if the sensor is missing/read fails:
//   {"ok":false,"error":"..."}
void handleThermal() {
  if (!thermalReady) {
    server.send(200, "application/json",
                "{\"ok\":false,\"error\":\"AMG8833 not detected\"}");
    return;
  }

  amg.readPixels(thermalPixels);

  float maxTemp = thermalPixels[0];
  int maxIndex = 0;
  for (int i = 1; i < AMG88xx_PIXEL_ARRAY_SIZE; i++) {
    if (thermalPixels[i] > maxTemp) {
      maxTemp = thermalPixels[i];
      maxIndex = i;
    }
  }

  int row = maxIndex / 8;
  int col = maxIndex % 8;

  String json = "{";
  json += "\"ok\":true,";
  json += "\"max_temp_c\":" + String(maxTemp, 2) + ",";
  json += "\"row\":" + String(row) + ",";
  json += "\"col\":" + String(col);
  json += "}";
  server.send(200, "application/json", json);
}

void handleServoX() {
  if (!server.hasArg("angle")) {
    server.send(400, "text/plain", "Missing angle parameter");
    return;
  }

  int angle = server.arg("angle").toInt();
  angleX = constrain(angle, 0, 180);
  servoX.write(apiToServoX(angleX));
  server.send(200, "text/plain", "X set to " + String(angleX));
}

void handleServoY() {
  if (!server.hasArg("angle")) {
    server.send(400, "text/plain", "Missing angle parameter");
    return;
  }

  int angle = server.arg("angle").toInt();
  angleY = constrain(angle, 0, 180);
  servoY.write(angleY);
  server.send(200, "text/plain", "Y set to " + String(angleY));
}

void handleTrigger() {
  if (!server.hasArg("state")) {
    server.send(400, "text/plain", "Missing state parameter");
    return;
  }

  String state = server.arg("state");

  if (state == "fire") {
    fire();
    server.send(200, "text/plain", "Trigger fired");
  } else if (state == "retract") {
    retract();
    server.send(200, "text/plain", "Trigger retracted");
  } else {
    server.send(400, "text/plain", "Invalid state. Use fire or retract");
  }
}

void handleMove() {
  if (!server.hasArg("axis")) {
    server.send(400, "text/plain", "Missing axis parameter");
    return;
  }

  if (!server.hasArg("dir")) {
    server.send(400, "text/plain", "Missing dir parameter");
    return;
  }

  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd parameter");
    return;
  }

  String axis = server.arg("axis");
  String dir = server.arg("dir");
  String cmd = server.arg("cmd");

  if (cmd != "start" && cmd != "stop") {
    server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    return;
  }

  bool start = (cmd == "start");

  if (axis == "x") {
    if (dir == "left") {
      moveRight = false;
      moveLeft = start;
    } else if (dir == "right") {
      moveLeft = false;
      moveRight = start;
    } else {
      server.send(400, "text/plain", "Invalid dir. Use left or right");
      return;
    }
  } else if (axis == "y") {
    if (dir == "up") {
      moveDown = false;
      moveUp = start;
    } else if (dir == "down") {
      moveUp = false;
      moveDown = start;
    } else {
      server.send(400, "text/plain", "Invalid dir. Use up or down");
      return;
    }
  } else {
    server.send(400, "text/plain", "Invalid axis. Use x or y");
    return;
  }

  server.send(200, "text/plain", "OK");
}

void fire() {
  digitalWrite(RETRACT_PIN, LOW);
  digitalWrite(FIRE_PIN, HIGH);
  angleTrigger = 180;
}

void retract() {
  digitalWrite(RETRACT_PIN, HIGH);
  digitalWrite(FIRE_PIN, LOW);
  angleTrigger = 90;
}