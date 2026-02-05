#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <../config.h>

const char *ssid = WIFI_SSID;
const char *password = WIFI_PASSWORD;
const int SERVO_X_PIN = 13;
const int SERVO_Y_PIN = 12;
const int SERVO_Z_PIN = 14;
const int MOVE_INTERVAL = 20; // ms between movement steps
const int RETRACT_PIN = 27;
const int FIRE_PIN = 26;
Servo servoX;
Servo servoY;
Servo servoZ;
bool surveillanceEnabled = true;
int angleX = 0;
int angleY = 0;
int direction = 0;
unsigned long lastMoveTime = 0;
WebServer server(80);

void handleSurveillance() {
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing cmd parameter");
    return;
  }

  String cmd = server.arg("cmd");

  if (cmd == "pause") {
    surveillanceEnabled = false;
    server.send(200, "text/plain", "Surveillance paused");
  } else if (cmd == "resume") {
    surveillanceEnabled = true;
    server.send(200, "text/plain", "Surveillance resumed");
  } else {
    server.send(400, "text/plain", "Invalid cmd. Use pause or resume.");
  }
}

void handleTrigger() {
  if (!server.hasArg("cmd")) {
    server.send(400, "text/plain", "Missing angle parameter");
    return;
  }

  String cmd = server.arg("cmd");

  if (cmd == "fire") {
    fire();
    server.send(200, "text/plain", "Trigger fired");
  } else if (cmd == "retract") {
    retract();
    server.send(200, "text/plain", "Trigger retracted");
  } else {
    server.send(400, "text/plain", "Invalid cmd. Use fire or retract.");
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

void setup() {
  Serial.begin(115200);
  servoX.attach(SERVO_X_PIN);
  servoY.attach(SERVO_Y_PIN);
  servoX.write(0);
  servoY.write(0);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nConnected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  server.on("/surveillance", HTTP_GET, handleSurveillance);
  server.on("/trigger", HTTP_GET, handleTrigger);
  server.begin();
  Serial.println("HTTP Server started.");
  pinMode(RETRACT_PIN, OUTPUT);
  pinMode(FIRE_PIN, OUTPUT);
  retract();
}

void loop() {
  server.handleClient();

  if (surveillanceEnabled) {
    unsigned long now = millis();

    if (now - lastMoveTime >= MOVE_INTERVAL) {
      lastMoveTime = now;
      direction++;
      direction %= 360;
      angleX = (sin(radians(direction)) * 90) + 90;
      angleY = (cos(radians(direction)) * 45) + 90;
      servoX.write(angleX);
      servoY.write(angleY);
    }
  }
}
