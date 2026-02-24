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
bool surveillanceEnabled = false;
bool moveUp = false;
bool moveDown = false;
bool moveLeft = false;
bool moveRight = false;
int angleX = 90;
int angleY = 90;
int direction = 0;
unsigned long lastMoveTime = 0;
WebServer server(80);

void setup() {
  Serial.begin(115200);
  servoX.attach(SERVO_X_PIN);
  servoY.attach(SERVO_Y_PIN);
  servoX.write(90);
  servoY.write(90);
  Serial.println("Starting Access Point...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apSSID, apPassword);
  IPAddress IP = WiFi.softAPIP();
  Serial.println("Access Point Started!");
  Serial.print("SSID: ");
  Serial.println(apSSID);
  Serial.print("IP Address: ");
  Serial.println(IP);

  server.on("/", HTTP_GET, []() {
    server.send(200, "text/html", R"rawliteral(
      <html>
          <head>
              <title>
                  Dashboard
              </title>
              <base href="./">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <style>
                  body {
                      margin: 0rem;
                      padding: 0rem;
                      background-color: #111;
                      color: #fff;
                      font-size: 1rem;
                      font-family: Arial, Helvetica, sans-serif;
                  }

                  a {
                      color: inherit;
                      text-decoration: none;
                  }

                  button {
                      padding: 1rem;
                      background-color: #5af;
                      color: #fff;
                      font-size: 1rem;
                      font-family: Arial, Helvetica, sans-serif;
                      border: none;
                      border-radius: 1rem;
                      cursor: pointer;
                      width: 5rem;
                      height: 5rem;
                      font-weight: bold;
                  }

                  form {
                      margin-block-end: 0rem;
                  }

                  input {
                      padding: 1rem;
                      width: 100%;
                      background-color: transparent;
                      color: #fff;
                      border: none;
                      border-bottom: 1px solid #5af;
                      font-size: 1rem;
                      font-family: Arial, Helvetica, sans-serif;
                  }

                  select {
                      padding: 1rem;
                      width: 100%;
                      background-color: transparent;
                      color: #fff;
                      border: none;
                      border-bottom: 1px solid #5af;
                      font-size: 1rem;
                      font-family: Arial, Helvetica, sans-serif;
                  }

                  textarea {
                      padding: 1rem;
                      width: 100%;
                      background-color: transparent;
                      color: #fff;
                      height: 10rem;
                      border: 1px solid #5af;
                      font-size: 1rem;
                      font-family: Arial, Helvetica, sans-serif;
                      resize: vertical;
                  }
              </style>
          </head>
          <body>
              <div style="
                  display: grid;
                  grid-template-rows: 1fr repeat(3, max-content);
                  height: 100%;
                  box-sizing: border-box;">
                  <div style="
                      padding: 1rem;">
                      <img style="
                          width: 100%;
                          height: 100%;
                          object-fit: contain;"
                          id="imgStream">
                  </div>
                  <div style="
                      display: grid;
                      grid-template-columns: repeat(3, 1fr);">
                      <div></div>
                      <div style="
                          padding: 1rem;
                          text-align: center;">
                          <button id="btnUp">
                              Up
                          </button>
                      </div>
                      <div></div>
                  </div>
                  <div style="
                      display: grid;
                      grid-template-columns: repeat(3, 1fr);">
                      <div style="
                          padding: 1rem;
                          text-align: center;">
                          <button id="btnLeft">
                              Left
                          </button>
                      </div>
                      <div style="
                          padding: 1rem;
                          text-align: center;">
                          <button id="btnShoot">
                              Shoot
                          </button>
                      </div>
                      <div style="
                          padding: 1rem;
                          text-align: center;">
                          <button id="btnRight">
                              Right
                          </button>
                      </div>
                  </div>
                  <div style="
                      display: grid;
                      grid-template-columns: repeat(3, 1fr);">
                      <div></div>
                      <div style="
                          padding: 1rem;
                          text-align: center;">
                          <button id="btnDown">
                              Down
                          </button>
                      </div>
                      <div></div>
                  </div>
              </div>
              <script>
                  CAMERA_IP = "192.168.4.2";
                  const imgStream = document.getElementById("imgStream");
                  const btnUp = document.getElementById("btnUp");
                  const btnLeft = document.getElementById("btnLeft");
                  const btnShoot = document.getElementById("btnShoot");
                  const btnRight = document.getElementById("btnRight");
                  const btnDown = document.getElementById("btnDown");
                  initialize();
                  
                  function initialize() {
                      for (let element of document.querySelectorAll("*")) {
                          element.style.setProperty("--test", "test");
                          element.style.removeProperty("--test");
                      }

                      imgStream.src = `http://${CAMERA_IP}:81/stream`;
                      attachButton(btnUp, "up");
                      attachButton(btnDown, "down");
                      attachButton(btnLeft, "left");
                      attachButton(btnRight, "right");
                      attachButton(btnShoot, "shoot");
                  }

                  function sendCommand(direction, cmd) {
                      fetch(`/control?direction=${direction}&cmd=${cmd}`)
                          .catch(err => console.error("Request failed:", err)).then(res => res.text()).then(data => console.log(data));
                  }

                  function attachButton(button, direction) {
                      let isPressed = false;

                      const start = (e) => {
                          e.preventDefault();
                          if (isPressed) return;
                          isPressed = true;
                          sendCommand(direction, "start");
                      };

                      const stop = (e) => {
                          e.preventDefault();
                          if (!isPressed) return;
                          isPressed = false;
                          sendCommand(direction, "stop");
                      };

                      button.addEventListener("mousedown", start);
                      button.addEventListener("mouseup", stop);
                      button.addEventListener("mouseleave", stop);
                      button.addEventListener("touchstart", start);
                      button.addEventListener("touchend", stop);
                      button.addEventListener("touchcancel", stop);
                  }
              </script>
          </body>
      </html>
    )rawliteral");
  });

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
        angleX += 1;

        if (angleX > 180) {
          angleX = 180;
        }
      }
    }

    servoX.write(angleX);
    servoY.write(angleY);
    Serial.print("X: ");
    Serial.print(angleX);
    Serial.print(" Y: ");
    Serial.println(angleY);
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
  } else if (direction == "shoot") {
    if (cmd == "start") {
      fire();
      server.send(200, "text/plain", "Trigger fired");
    } else if (cmd == "stop") {
      retract();
      server.send(200, "text/plain", "Trigger retracted");
    } else {
      server.send(400, "text/plain", "Invalid cmd. Use start or stop");
    }
  } else {
    server.send(400, "text/plain", "Invalid direction. Use up, down, left, or right");
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