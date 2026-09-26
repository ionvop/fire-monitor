/*
 * AMG8833 thermal camera -> Arduino Uno -> USB serial bridge.
 *
 * Wiring (AMG8833 breakout -> Arduino Uno):
 *   VIN -> 5V
 *   GND -> GND
 *   SCL -> A5
 *   SDA -> A4
 *
 * A4/A5 are the Uno's hardware I2C pins, so the Wire library talks to the
 * sensor with no extra pin configuration.
 *
 * Each loop the sketch reads the 8x8 (64 pixel) temperature grid, finds the
 * pixel with the highest temperature, and prints one line over serial:
 *
 *   HOT,<temp_c>,<row>,<col>
 *
 * where <temp_c> is in degrees Celsius (2 decimals) and <row>/<col> are the
 * 0-based grid coordinates of the hottest pixel. The "HOT," prefix lets the
 * Python reader ignore any boot/error text the board emits.
 *
 * Requires the Adafruit AMG88xx library (Library Manager: "Adafruit AMG88xx").
 */

#include <Wire.h>
#include <Adafruit_AMG88xx.h>

// Serial baud rate. Must match the Python reader (default 115200).
const long SERIAL_BAUD = 115200;

// Delay between reads (ms). The AMG8833 refreshes at ~10 Hz, so 100 ms is a
// good match and keeps the serial stream readable.
const unsigned long READ_INTERVAL_MS = 100;

Adafruit_AMG88xx amg;

// 8x8 = 64 pixels, stored row-major (index = row * 8 + col).
float pixels[AMG88xx_PIXEL_ARRAY_SIZE];

void setup() {
  Serial.begin(SERIAL_BAUD);

  // Give the serial port a moment to come up before the first read.
  delay(500);

  if (!amg.begin()) {
    // Sensor not found: report once and halt so the Python side sees a clear
    // error instead of a stream of garbage values.
    Serial.println("ERROR,AMG8833 not detected. Check wiring (VIN=5V, GND=GND, SCL=A5, SDA=A4).");
    while (true) {
      delay(1000);
    }
  }

  Serial.println("READY,AMG8833 initialized");
}

void loop() {
  amg.readPixels(pixels);

  // Find the hottest pixel and remember where it is.
  float maxTemp = pixels[0];
  int maxIndex = 0;
  for (int i = 1; i < AMG88xx_PIXEL_ARRAY_SIZE; i++) {
    if (pixels[i] > maxTemp) {
      maxTemp = pixels[i];
      maxIndex = i;
    }
  }

  int row = maxIndex / 8;
  int col = maxIndex % 8;

  // HOT,<temp_c>,<row>,<col>
  Serial.print("HOT,");
  Serial.print(maxTemp, 2);
  Serial.print(",");
  Serial.print(row);
  Serial.print(",");
  Serial.println(col);

  delay(READ_INTERVAL_MS);
}