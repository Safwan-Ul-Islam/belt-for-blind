# Belt for Blind

ESP32 + 3 × HC-SR04 ultrasonic sensors, a vibration motor for alerts and an MPU6050 IMU. The belt measures distances and vibrates when something is too close. It pauses while the wearer sits, to save battery, and wakes when they stand up or walk.

## Wiring

Pin names below are as printed on the ESP32 DevKit board (`D25` = GPIO 25). `VIN` gives 5V when the board is powered over USB.

| Sensor | VCC | GND | TRIG | ECHO |
|--------|-----|-----|------|------|
| Left   | VIN | GND | D25  | D34  |
| Center | VIN | GND | D26  | D35  |
| Right  | VIN | GND | D27  | D32  |

IMU (MPU6050 / GY-521 module): `VCC` → `3V3`, `GND` → `GND`, `SDA` → `D21`, `SCL` → `D22`. Fix it firmly to the belt, because sitting is detected from its tilt.

Three 3V coin vibration motors, one per side, each switched by a logic-level N-channel MOSFET:

| Motor | Signal pin |
|-------|-----------|
| Left   | `D13` |
| Center | `D33` |
| Right  | `D4`  |

For each motor:

| From | To |
|------|----|
| Signal pin | 220Ω resistor → MOSFET gate |
| MOSFET gate | 10kΩ resistor → `GND` (keeps the motor off while the ESP32 starts) |
| MOSFET source | `GND` |
| MOSFET drain | motor − (black) |
| Motor + (red) | `3V3` |
| 1N4007 diode across the motor | striped end on motor + / `3V3` |

The MOSFET must turn fully on at 3.3V (e.g. IRLZ44N, AO3400); IRFZ44N or IRF540N won't.

Each motor runs when its sensor sees something too close: Left or Right under 15 cm, Center under 30 cm (set per sensor by `alertCm` in `src/main.cpp`).

**Important:** the HC-SR04 ECHO pin outputs 5V, but ESP32 pins are 3.3V. Put a voltage divider on each ECHO line
(ECHO → 1kΩ → GPIO, and GPIO → 2kΩ → GND), or use HC-SR04P / RCWL-1601 sensors that run at 3.3V.

## Run

1. Open this folder in VS Code (PlatformIO extension installed).
2. Plug in the ESP32 over USB.
3. Click **Upload** (→ arrow in the bottom status bar), then **Serial Monitor** (plug icon).

Expected output:

```
---------------- distance to obstacle ----------------
  Left      42 cm   ####                  VERY CLOSE
  Center     --      nothing in front
  Right   NO SIGNAL - check this sensor's wires
  Motor   off
  IMU     tilt   3 deg   motion 0.012 g
```

Move your hand in front of each sensor. If its number changes, that sensor works.

- `nothing in front`: the sensor works, but nothing within ~5 m reflected the sound back.
- `NO SIGNAL`: the sensor isn't answering at all. Check its Trig, Echo, VCC and GND wires.

The belt pauses after the wearer has been still for 5 s and tilted more than 20° from upright. It wakes when they return within 12° of upright or walk for 1 s. If the IMU isn't found, the belt stays on. Tune these limits from the `IMU` line, using the constants at the top of `src/main.cpp`.

## Live view in the browser

A web page that draws the ESP32, the three sensors, the three vibration motors and the MPU6050, and shows each detection, which motors are vibrating, the IMU's tilt and motion, and when the belt is paused because the wearer sits.

1. Close the Serial Monitor: only one program can use the USB port at a time.
2. Run, from this folder:
   ```
   ~/.platformio/penv/bin/python tools/live-view/server.py
   ```
3. Open http://localhost:8000

Stop it with Ctrl+C before uploading new firmware.

## 3D model (Blender)

`3d-model/belt_for_blind.blend` is a to-scale model of the breadboard prototype. Rebuild it with:
```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P 3d-model/build_model.py -- 3d-model/belt_for_blind.blend
```

The realistic background is the CC0 [Artist Workshop](https://polyhaven.com/a/artist_workshop) HDRI from Poly Haven. It is not in git (25 MB), so download it once, or the background shows pink:
```
mkdir -p 3d-model/hdri && curl -L -o 3d-model/hdri/artist_workshop_4k.hdr https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/artist_workshop_4k.hdr
```

To make it follow the real sensors: start the live-view server (above), open the file, go to the **Scripting** tab and click **Run Script** on `live_link.py`. Click it again to stop.
