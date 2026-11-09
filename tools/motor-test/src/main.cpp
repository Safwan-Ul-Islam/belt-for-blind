// Motor wiring test: switches every motor pin on and off once a second, no sensors needed.
#include <Arduino.h>

const uint8_t MOTOR_PINS[] = {13, 33, 4}; // Left, Center, Right
const char *MOTOR_NAMES[] = {"Left (D13)", "Center (D33)", "Right (D4)"};

void setup() {
  Serial.begin(115200);
  for (uint8_t pin : MOTOR_PINS) pinMode(pin, OUTPUT);
}

void loop() {
  for (bool on : {true, false}) {
    for (uint8_t pin : MOTOR_PINS) digitalWrite(pin, on ? HIGH : LOW);
    Serial.printf("All motor pins %s: ", on ? "ON " : "off");
    for (const char *name : MOTOR_NAMES) Serial.printf("%s ", name);
    Serial.println();
    delay(1000);
  }
}
