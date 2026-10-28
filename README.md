# Belt for Blind

ESP32 + 3 × HC-SR04 ultrasonic sensors. This first sketch only checks that each sensor triggers, gets an echo, and calculates a distance.

## Wiring

| Sensor | VCC | GND | TRIG    | ECHO    |
|--------|-----|-----|---------|---------|
| Left   | 5V  | GND | GPIO 25 | GPIO 34 |
| Center | 5V  | GND | GPIO 26 | GPIO 35 |
| Right  | 5V  | GND | GPIO 27 | GPIO 32 |

**Important:** the HC-SR04 ECHO pin outputs 5V, but ESP32 pins are 3.3V. Put a voltage divider on each ECHO line
(ECHO → 1kΩ → GPIO, and GPIO → 2kΩ → GND), or use HC-SR04P / RCWL-1601 sensors that run at 3.3V.

## Run

1. Open this folder in VS Code (PlatformIO extension installed).
2. Plug in the ESP32 over USB.
3. Click **Upload** (→ arrow in the bottom status bar), then **Serial Monitor** (plug icon).

Expected output:

```
Left  :   42.3 cm  |  Center:  120.8 cm  |  Right :  NO ECHO (check wiring)
```

Move your hand in front of each sensor. If its number changes, that sensor works.
