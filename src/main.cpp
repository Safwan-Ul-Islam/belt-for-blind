// Belt for Blind
// Fires 3 HC-SR04 sensors one at a time, prints each distance to Serial and
// vibrates the motor on that side when something is too close. An MPU6050
// pauses the belt while the wearer sits, to save battery, and wakes it when
// they stand up or walk.

#include <Arduino.h>
#include <Wire.h>
#include <esp_sleep.h>

struct UltrasonicSensor {
  const char *name;
  uint8_t trigPin;
  uint8_t echoPin;
  float alertCm;    // vibrate when something is closer than this
  uint8_t motorPin; // this side's vibration motor, switched by a MOSFET: HIGH = vibrate
};

// Center faces where you walk, so it warns earlier
UltrasonicSensor sensors[] = {
  {"Left",   25, 34, 15, 13},
  {"Center", 26, 35, 30, 33},
  {"Right",  27, 32, 15, 4},
};
const int SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

// MPU6050 on I2C
const uint8_t IMU_SDA_PIN = 21;
const uint8_t IMU_SCL_PIN = 22;
const uint8_t IMU_ADDRESS = 0x68;
const uint8_t IMU_REG_PWR_MGMT_1 = 0x6B;
const uint8_t IMU_REG_ACCEL_XOUT_H = 0x3B;
const float IMU_LSB_PER_G = 16384.0; // default +/-2 g range

// Sitting detection. Tune these from the "IMU" line printed to Serial.
const float SIT_TILT_DEG = 20;    // leaning this far from upright can mean sitting...
const unsigned long SIT_AFTER_MS = 5000; // ...once the wearer has been still this long
const float STAND_TILT_DEG = 12;  // back within this tilt means standing again
const float STILL_MOTION_G = 0.03; // below this the wearer counts as still
const float WALK_MOTION_G = 0.08;  // above this the wearer is moving...
const unsigned long WALK_AFTER_MS = 1000; // ...and this long of it counts as walking

const unsigned long IMU_SAMPLE_MS = 20;
const unsigned long SITTING_POLL_MS = 200;     // ESP32 sleeps between checks while sitting
const unsigned long SITTING_PRINT_MS = 2000; // often enough for the live view to stay connected

// Filter time constants, in seconds
const float GRAVITY_TAU_S = 0.5;
const float MOTION_TAU_S = 0.5;
const float UPRIGHT_TAU_S = 5.0;

// A working sensor raises ECHO within a few ms of the trigger
const unsigned long ECHO_START_TIMEOUT_US = 10000;
// ~30 ms covers ~5 m round trip; a longer echo means nothing in range
const unsigned long ECHO_TIMEOUT_US = 30000;
const float SOUND_SPEED_CM_PER_US = 0.0343;

struct Vec3 {
  float x, y, z;
};

Vec3 blend(const Vec3 &from, const Vec3 &to, float amount) {
  return {from.x + (to.x - from.x) * amount,
          from.y + (to.y - from.y) * amount,
          from.z + (to.z - from.z) * amount};
}

float length(const Vec3 &v) {
  return sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

float angleDeg(const Vec3 &a, const Vec3 &b) {
  float lengths = length(a) * length(b);
  if (lengths == 0) return 0;
  float cosine = (a.x * b.x + a.y * b.y + a.z * b.z) / lengths;
  return degrees(acos(constrain(cosine, -1.0f, 1.0f)));
}

bool imuOk = false;
bool imuHasData = false;
bool sitting = false;
Vec3 gravity;  // smoothed acceleration, which shows which way is down
Vec3 upright;  // gravity direction when the wearer stands; refreshed while walking
float motion = 0; // smoothed shaking, in g
float tiltDeg = 0;
unsigned long lastSampleMs = 0;
unsigned long lastMovedMs = 0;  // last time motion was above STILL_MOTION_G
unsigned long lastCalmMs = 0;   // last time motion was below WALK_MOTION_G

bool startImu() {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(IMU_REG_PWR_MGMT_1);
  Wire.write(0); // the MPU6050 starts asleep; wake it
  imuHasData = false;
  return Wire.endTransmission() == 0;
}

bool readAccel(Vec3 &accel) {
  Wire.beginTransmission(IMU_ADDRESS);
  Wire.write(IMU_REG_ACCEL_XOUT_H);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(IMU_ADDRESS, (uint8_t)6) != 6) return false;

  int16_t raw[3];
  for (int i = 0; i < 3; i++) {
    uint16_t high = Wire.read();
    raw[i] = (int16_t)((high << 8) | Wire.read());
  }
  accel = {raw[0] / IMU_LSB_PER_G, raw[1] / IMU_LSB_PER_G, raw[2] / IMU_LSB_PER_G};
  return true;
}

// Reads the IMU and decides whether the wearer is sitting.
// Without a working IMU the belt always stays on, which is the safe choice.
void updateImu() {
  if (!imuOk) imuOk = startImu();
  Vec3 accel;
  if (!imuOk || !readAccel(accel)) {
    imuOk = false;
    sitting = false;
    return;
  }

  unsigned long now = millis();
  if (!imuHasData) {
    gravity = upright = accel; // assume upright until walking shows otherwise
    motion = 0;
    lastMovedMs = lastCalmMs = lastSampleMs = now;
    imuHasData = true;
    return;
  }

  float dt = (now - lastSampleMs) / 1000.0;
  lastSampleMs = now;
  Vec3 shake = {accel.x - gravity.x, accel.y - gravity.y, accel.z - gravity.z};
  motion += (length(shake) - motion) * dt / (MOTION_TAU_S + dt);
  gravity = blend(gravity, accel, dt / (GRAVITY_TAU_S + dt));
  tiltDeg = angleDeg(gravity, upright);

  if (motion >= STILL_MOTION_G) lastMovedMs = now;
  if (motion < WALK_MOTION_G) lastCalmMs = now;
  bool walking = now - lastCalmMs >= WALK_AFTER_MS;

  // People walk upright, so walking corrects the reference if the belt shifted
  if (walking) upright = blend(upright, gravity, dt / (UPRIGHT_TAU_S + dt));

  if (sitting) {
    if (tiltDeg < STAND_TILT_DEG || walking) sitting = false;
  } else if (tiltDeg > SIT_TILT_DEG && now - lastMovedMs >= SIT_AFTER_MS) {
    sitting = true;
  }
}

// Like delay(), but keeps watching the IMU
void waitWatchingImu(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) {
    updateImu();
    delay(IMU_SAMPLE_MS);
  }
}

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

void setMotors(bool on) {
  for (int i = 0; i < SENSOR_COUNT; i++) digitalWrite(sensors[i].motorPin, on ? HIGH : LOW);
}

void setup() {
  for (int i = 0; i < SENSOR_COUNT; i++) pinMode(sensors[i].motorPin, OUTPUT);
  setMotors(false);
  Serial.begin(115200);
  delay(500);
  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(sensors[i].trigPin, OUTPUT);
    digitalWrite(sensors[i].trigPin, LOW);
    pinMode(sensors[i].echoPin, INPUT);
  }
  Wire.begin(IMU_SDA_PIN, IMU_SCL_PIN);
  imuOk = startImu();
  Serial.println("Belt for Blind started");
  if (!imuOk) Serial.println("IMU not found: belt stays on. Check its VCC, GND, SDA and SCL wires.");

  // Motor self-test: each motor buzzes once in turn, so the wearer knows the belt is on
  for (int i = 0; i < SENSOR_COUNT; i++) {
    Serial.printf("Motor test: %s\n", sensors[i].name);
    digitalWrite(sensors[i].motorPin, HIGH);
    delay(500);
    digitalWrite(sensors[i].motorPin, LOW);
    delay(300);
  }
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

void printImuLine() {
  // gravity: which way is down, in the sensor's own axes (used by the 3D view to tilt the model)
  if (imuOk) Serial.printf("  IMU     tilt %3.0f deg   motion %.3f g   gravity %5.2f %5.2f %5.2f\n",
                           tiltDeg, motion, gravity.x, gravity.y, gravity.z);
  else       Serial.println("  IMU     NOT FOUND - belt stays on, check its wires");
}

// Sensors and motor stay off; the ESP32 sleeps and only wakes to check the IMU
void pauseWhileSitting() {
  setMotors(false);
  Serial.println("--- wearer is sitting: sensors and motors paused ---");
  unsigned long lastPrintMs = millis();
  while (sitting) {
    Serial.flush(); // serial output stops during sleep
    esp_sleep_enable_timer_wakeup(SITTING_POLL_MS * 1000);
    esp_light_sleep_start();
    updateImu();
    if (millis() - lastPrintMs >= SITTING_PRINT_MS) {
      printImuLine();
      lastPrintMs = millis();
    }
  }
  Serial.println("--- wearer is up: belt back on ---");
}

void loop() {
  updateImu();
  if (sitting) {
    pauseWhileSitting();
    return;
  }

  Serial.println("---------------- distance to obstacle ----------------");
  bool tooClose[SENSOR_COUNT];
  bool anyTooClose = false;
  for (int i = 0; i < SENSOR_COUNT; i++) {
    float cm = 0;
    ReadResult r = readDistanceCm(sensors[i], cm);
    printSensorLine(sensors[i].name, r, cm);
    tooClose[i] = r == READ_OK && cm < sensors[i].alertCm;
    anyTooClose |= tooClose[i];
    waitWatchingImu(60); // let echoes die out so sensors don't hear each other
  }

  // Each side vibrates its own motor, so the wearer feels where the obstacle is
  Serial.print(anyTooClose ? "  Motor   ON  -" : "  Motor   off");
  for (int i = 0; i < SENSOR_COUNT; i++) {
    digitalWrite(sensors[i].motorPin, tooClose[i] ? HIGH : LOW);
    if (tooClose[i]) Serial.printf(" %s (<%.0f cm)", sensors[i].name, sensors[i].alertCm);
  }
  Serial.println();
  printImuLine();
  Serial.println();
  waitWatchingImu(150);
}
