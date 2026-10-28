// Belt for Blind - ultrasonic sensor test
// Fires 3 HC-SR04 sensors one at a time and prints each distance to Serial.

#include <Arduino.h>

struct UltrasonicSensor {
  const char *name;
  uint8_t trigPin;
  uint8_t echoPin;
};

UltrasonicSensor sensors[] = {
  {"Left",   25, 34},
  {"Center", 26, 35},
  {"Right",  27, 32},
};
const int SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

// ~30 ms covers ~5 m round trip; beyond that we treat it as "no echo"
const unsigned long ECHO_TIMEOUT_US = 30000;
const float SOUND_SPEED_CM_PER_US = 0.0343;

// Returns distance in cm, or -1 if no echo came back
float readDistanceCm(const UltrasonicSensor &s) {
  digitalWrite(s.trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(s.trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(s.trigPin, LOW);

  unsigned long duration = pulseIn(s.echoPin, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return -1;
  return duration * SOUND_SPEED_CM_PER_US / 2.0;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(sensors[i].trigPin, OUTPUT);
    digitalWrite(sensors[i].trigPin, LOW);
    pinMode(sensors[i].echoPin, INPUT);
  }
  Serial.println("Belt for Blind - ultrasonic test started");
}

void loop() {
  for (int i = 0; i < SENSOR_COUNT; i++) {
    float d = readDistanceCm(sensors[i]);
    Serial.printf("%-6s: ", sensors[i].name);
    if (d < 0) Serial.print("NO ECHO (check wiring)");
    else       Serial.printf("%6.1f cm", d);
    Serial.print(i < SENSOR_COUNT - 1 ? "  |  " : "\n");
    delay(60); // let echoes die out so sensors don't hear each other
  }
  delay(200);
}
