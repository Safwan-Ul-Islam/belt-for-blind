// Belt for Blind - ultrasonic sensor test
// Fires 3 HC-SR04 sensors one at a time and prints each distance to Serial.

#include <Arduino.h>

struct UltrasonicSensor {
  const char *name;
  uint8_t trigPin;
  uint8_t echoPin;
  float alertCm; // buzz when something is closer than this
};

// Center faces where you walk, so it warns earlier
UltrasonicSensor sensors[] = {
  {"Left",   25, 34, 15},
  {"Center", 26, 35, 30},
  {"Right",  27, 32, 15},
};
const int SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

// Active buzzer (TMB12A05): HIGH = sound
const uint8_t BUZZER_PIN = 13;

// A working sensor raises ECHO within a few ms of the trigger
const unsigned long ECHO_START_TIMEOUT_US = 10000;
// ~30 ms covers ~5 m round trip; a longer echo means nothing in range
const unsigned long ECHO_TIMEOUT_US = 30000;
const float SOUND_SPEED_CM_PER_US = 0.0343;

enum ReadResult { READ_OK, NO_SIGNAL, OUT_OF_RANGE };

// Waits for pin to reach level; returns false if timeoutUs passes first
bool waitForLevel(uint8_t pin, int level, unsigned long timeoutUs) {
  unsigned long start = micros();
  while (digitalRead(pin) != level) {
    if (micros() - start > timeoutUs) return false;
  }
  return true;
}

// NO_SIGNAL: ECHO never went HIGH, so the sensor isn't answering (wiring).
// OUT_OF_RANGE: sensor answered but nothing reflected the sound back.
ReadResult readDistanceCm(const UltrasonicSensor &s, float &distanceCm) {
  digitalWrite(s.trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(s.trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(s.trigPin, LOW);

  if (!waitForLevel(s.echoPin, HIGH, ECHO_START_TIMEOUT_US)) return NO_SIGNAL;
  unsigned long start = micros();
  if (!waitForLevel(s.echoPin, LOW, ECHO_TIMEOUT_US)) return OUT_OF_RANGE;

  distanceCm = (micros() - start) * SOUND_SPEED_CM_PER_US / 2.0;
  return READ_OK;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(sensors[i].trigPin, OUTPUT);
    digitalWrite(sensors[i].trigPin, LOW);
    pinMode(sensors[i].echoPin, INPUT);
  }
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("Belt for Blind - ultrasonic test started");
}

// Labels shown next to each reading
const float VERY_CLOSE_CM = 50;
const float CLOSE_CM = 150;

// Distance bar: one '#' per 10 cm, up to 2 m
const int BAR_CM_PER_CHAR = 10;
const int BAR_MAX_CHARS = 20;

const char *describeDistance(float cm) {
  if (cm < VERY_CLOSE_CM) return "VERY CLOSE";
  if (cm < CLOSE_CM)      return "close";
  return "far";
}

void printSensorLine(const char *name, ReadResult r, float cm) {
  Serial.printf("  %-7s ", name);
  if (r == NO_SIGNAL) {
    Serial.println("NO SIGNAL - check this sensor's wires");
    return;
  }
  if (r == OUT_OF_RANGE) {
    Serial.println("   --      nothing in front");
    return;
  }

  char bar[BAR_MAX_CHARS + 1];
  int chars = min((int)(cm / BAR_CM_PER_CHAR), BAR_MAX_CHARS);
  memset(bar, '#', chars);
  bar[chars] = '\0';
  Serial.printf("%4.0f cm   %-*s  %s\n", cm, BAR_MAX_CHARS, bar, describeDistance(cm));
}

void loop() {
  Serial.println("---------------- distance to obstacle ----------------");
  const UltrasonicSensor *trigger = nullptr; // first sensor that is too close
  for (int i = 0; i < SENSOR_COUNT; i++) {
    float cm = 0;
    ReadResult r = readDistanceCm(sensors[i], cm);
    printSensorLine(sensors[i].name, r, cm);
    if (r == READ_OK && cm < sensors[i].alertCm && !trigger) trigger = &sensors[i];
    delay(60); // let echoes die out so sensors don't hear each other
  }

  digitalWrite(BUZZER_PIN, trigger ? HIGH : LOW);
  if (trigger) Serial.printf("  Buzzer  ON  - %s closer than %.0f cm!\n", trigger->name, trigger->alertCm);
  else         Serial.println("  Buzzer  off");
  Serial.println();
  delay(150);
}
