# Belt for Blind

ESP32 + 3 × HC-SR04 ultrasonic sensors. This first sketch only checks that each sensor triggers, gets an echo, and calculates a distance.

## Wiring

Pin names below are as printed on the ESP32 DevKit board (`D25` = GPIO 25). `VIN` gives 5V when the board is powered over USB.

| Sensor | VCC | GND | TRIG | ECHO |
|--------|-----|-----|------|------|
| Left   | VIN | GND | D25  | D34  |
| Center | VIN | GND | D26  | D35  |
| Right  | VIN | GND | D27  | D32  |

Buzzer (TMB12A05, active): **+** leg (the longer one) → `D13`, **−** leg → `GND`. It sounds when Left or Right sees something closer than 15 cm, or Center closer than 30 cm (set per sensor by `alertCm` in `src/main.cpp`).

**Important:** the HC-SR04 ECHO pin outputs 5V, but ESP32 pins are 3.3V. Put a voltage divider on each ECHO line
(ECHO → 1kΩ → GPIO, and GPIO → 2kΩ → GND), or use HC-SR04P / RCWL-1601 sensors that run at 3.3V.

## Run

1. Open this folder in VS Code (PlatformIO extension installed).
2. Plug in the ESP32 over USB.
3. Click **Upload** (→ arrow in the bottom status bar), then **Serial Monitor** (plug icon).

Expected output:

```
Left  :   42.3 cm  |  Center: nothing in range  |  Right : NO SIGNAL (check wiring)
```

Move your hand in front of each sensor. If its number changes, that sensor works.

- `nothing in range`: the sensor works, but nothing within ~5 m reflected the sound back.
- `NO SIGNAL (check wiring)`: the sensor isn't answering at all. Check its Trig, Echo, VCC and GND wires.

## Live view in the browser

A web page that draws the ESP32 and the three sensors and shows each detection live.

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
