#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>

const char* apSSID = "ESP32-Turret";
const char* apPassword = "12345678";
const int SERVO_X_PIN = 13;
const int SERVO_Y_PIN = 12;
const int MOVE_INTERVAL = 20; // ms between movement steps
const int RETRACT_PIN = 27;
const int FIRE_PIN = 26;
Servo servoX;
Servo servoY;
Servo servoZ;
bool surveillanceEnabled = true;
bool moveUp = false;
bool moveDown = false;
bool moveLeft = false;
bool moveRight = false;
int angleX = 0;
int angleY = 0;
int direction = 0;
unsigned long lastMoveTime = 0;
WebServer server(80);

void setup() {
  Serial.begin(115200);
  servoX.attach(SERVO_X_PIN);
  servoY.attach(SERVO_Y_PIN);
  servoX.write(0);
  servoY.write(0);
  Serial.println("Starting Access Point...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID, apPassword);
  IPAddress IP = WiFi.softAPIP();
  Serial.println("Access Point Started!");
  Serial.print("SSID: ");
  Serial.println(apSSID);
  Serial.print("IP Address: ");
  Serial.println(IP);
  server.on("/surveillance", HTTP_GET, handleSurveillance);
  server.on("/trigger", HTTP_GET, handleTrigger);
  server.on("/control", HTTP_GET, handleControl);
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

    if (surveillanceEnabled) {
      direction++;
      direction %= 360;
      angleX = (sin(radians(direction)) * 90) + 90;
      angleY = (cos(radians(direction)) * 45) + 90;
    } else {
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
        angleY += 1;

        if (angleY > 180) {
          angleY = 180;
        }
      }
    }

    servoX.write(angleX);
    servoY.write(angleY);
  }
}

void handleSurveillance() {
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd parameter");
    return;
  }

  String cmd = server.arg("cmd");

  if (cmd == "start") {
    surveillanceEnabled = true;
    server.send(200, "text/plain", "Surveillance started");
  } else if (cmd == "stop") {
    surveillanceEnabled = false;
    server.send(200, "text/plain", "Surveillance stopped");
  } else {
    server.send(400, "text/plain", "Invalid cmd. Use start or stop");
  }
}

void handleTrigger() {
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd parameter");
    return;
  }

  String cmd = server.arg("cmd");

  if (cmd == "start") {
    fire();
    server.send(200, "text/plain", "Trigger fired");
  } else if (cmd == "stop") {
    retract();
    server.send(200, "text/plain", "Trigger retracted");
  } else {
    server.send(400, "text/plain", "Invalid cmd. Use start or stop");
  }
}

void handleControl() {
  if (!server.hasArg("direction")) {
    server.send(400, "text/plain", "Missing direction parameter");
    return;
  }
  
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd parameter");
    return;
  }

  String direction = server.arg("direction");
  String cmd = server.arg("cmd");

  if (direction == "up") {
    if (cmd == "start") {
      moveUp = true;
      server.send(200, "text/plain", "Started moving up");
    } else if (cmd == "stop") {
      moveUp = false;
      server.send(200, "text/plain", "Stopped moving up");
    } else {
      server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    }
  } else if (direction == "down") {
    if (cmd == "start") {
      moveDown = true;
      server.send(200, "text/plain", "Started moving down");
    } else if (cmd == "stop") {
      moveDown = false;
      server.send(200, "text/plain", "Stopped moving down");
    } else {
      server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    }
  } else if (direction == "left") {
    if (cmd == "start") {
      moveLeft = true;
      server.send(200, "text/plain", "Started moving left");
    } else if (cmd == "stop") {
      moveLeft = false;
      server.send(200, "text/plain", "Stopped moving left");
    } else {
      server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    }
  } else if (direction == "right") {
    if (cmd == "start") {
      moveRight = true;
      server.send(200, "text/plain", "Started moving right");
    } else if (cmd == "stop") {
      moveRight = false;
      server.send(200, "text/plain", "Stopped moving right");
    } else {
      server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    }
  } else {
    server.send(400, "text/plain", "Invalid direction. Use up, downm, left, or right");
  }
}

void fire() {
  digitalWrite(RETRACT_PIN, LOW);
  digitalWrite(FIRE_PIN, HIGH);
}

void retract() {
  digitalWrite(RETRACT_PIN, HIGH);
  digitalWrite(FIRE_PIN, LOW);
}