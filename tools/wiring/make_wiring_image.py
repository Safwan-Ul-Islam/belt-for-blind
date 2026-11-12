"""Draws docs/wiring-pictorial.svg: the Belt for Blind wiring with parts drawn as they look.

Every part, pin, wire and tag sits in a <g data-part="..."> group, so the live web page can make
them clickable. Run:  python3 tools/wiring/make_wiring_image.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "docs" / "wiring-pictorial.svg"
W, H = 1720, 1360
INK, MUTED = "#1f2937", "#6b7280"
C = {"5V": "#dc2626", "3V3": "#ea580c", "GND": "#111827", "trig": "#ca8a04", "echo": "#2563eb",
     "sig": "#db2777", "sda": "#16a34a", "scl": "#7c3aed", "red": "#dc2626", "black": "#111827"}
BANDS = {"brown": "#7a4a2a", "black": "#151515", "red": "#d02a2a", "orange": "#ef7d1a", "gold": "#c9a227"}
o = []

DEFS = """<defs>
<linearGradient id="metal" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f3f4f6"/><stop offset=".5" stop-color="#c7ccd3"/><stop offset="1" stop-color="#9aa1aa"/></linearGradient>
<radialGradient id="can" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#fbfcfd"/><stop offset=".6" stop-color="#c3c9d1"/><stop offset="1" stop-color="#7e8792"/></radialGradient>
<pattern id="mesh" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="4" fill="#4a5059"/><circle cx="2" cy="2" r="1.1" fill="#1b1e23"/></pattern>
<linearGradient id="resbody" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f3e2bf"/><stop offset=".5" stop-color="#e2c896"/><stop offset="1" stop-color="#c9ad78"/></linearGradient>
<linearGradient id="resbodyv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f3e2bf"/><stop offset=".5" stop-color="#e2c896"/><stop offset="1" stop-color="#c9ad78"/></linearGradient>
<linearGradient id="black3d" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3a3d42"/><stop offset=".45" stop-color="#1b1d21"/><stop offset="1" stop-color="#0c0d0f"/></linearGradient>
<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity=".25"/></filter>
</defs>"""


def begin(part):
    """Start a clickable group; everything drawn until end() belongs to this part."""
    o.append(f'<g data-part="{part}">')


def end():
    o.append("</g>")


def wire(pts, color, w=4.5):
    o.append(f'<polyline points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="none" stroke="{color}" '
             f'stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')


def text(x, y, s, size=17, anchor="start", weight=500, fill=INK):
    o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
             f'text-anchor="{anchor}" dominant-baseline="middle">{s}</text>')


def dot(x, y, color=INK):
    o.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')


def tag(x, y, label, align="left"):
    """Connection label: every tag with the same name is joined together."""
    w = 18 + 11 * len(label)
    x0 = {"left": x, "right": x - w, "center": x - w / 2}[align]
    begin(f"net-{label}")
    o.append(f'<rect x="{x0}" y="{y - 15}" width="{w}" height="30" rx="15" fill="{C[label]}" filter="url(#shadow)"/>')
    text(x0 + w / 2, y + 1, label, 15, "middle", 800, "#fff")
    end()


def resistor_h(x1, x2, y, bands, label):
    wire([(x1, y), (x1 + 12, y)], "#9ca3af", 3); wire([(x2 - 12, y), (x2, y)], "#9ca3af", 3)
    o.append(f'<rect x="{x1 + 10}" y="{y - 12}" width="{x2 - x1 - 20}" height="24" rx="11" fill="url(#resbody)" stroke="#a88b55" filter="url(#shadow)"/>')
    for i, b in enumerate(bands):
        bx = x1 + 22 + i * 11 + (10 if i == 3 else 0)
        o.append(f'<rect x="{bx}" y="{y - 12}" width="6" height="24" fill="{BANDS[b]}"/>')
    if label:
        text((x1 + x2) / 2, y + 30, label, 15, "middle", 800)


def resistor_v(x, y1, y2, bands, label):
    wire([(x, y1), (x, y1 + 12)], "#9ca3af", 3); wire([(x, y2 - 12), (x, y2)], "#9ca3af", 3)
    o.append(f'<rect x="{x - 12}" y="{y1 + 10}" width="24" height="{y2 - y1 - 20}" rx="11" fill="url(#resbodyv)" stroke="#a88b55" filter="url(#shadow)"/>')
    for i, b in enumerate(bands):
        by = y1 + 22 + i * 11 + (10 if i == 3 else 0)
        o.append(f'<rect x="{x - 12}" y="{by}" width="24" height="6" fill="{BANDS[b]}"/>')
    text(x + 22, (y1 + y2) / 2, label, 15, "start", 800)


def hcsr04(y0, name):
    """HC-SR04 drawn on its side: two silver transducers, header pins on the right."""
    o.append(f'<rect x="60" y="{y0 - 10}" width="165" height="140" rx="8" fill="#1f5fb0" stroke="#163f73" stroke-width="2" filter="url(#shadow)"/>')
    for cy in (y0 + 22, y0 + 98):
        o.append(f'<circle cx="112" cy="{cy}" r="31" fill="url(#can)" stroke="#6b737d" stroke-width="1.5"/>')
        o.append(f'<circle cx="112" cy="{cy}" r="23" fill="url(#mesh)" stroke="#2a2e35" stroke-width="2"/>')
    o.append(f'<rect x="152" y="{y0 + 52}" width="14" height="16" rx="7" fill="url(#metal)"/>')
    text(160, y0 - 24, f"{name} sensor", 17, "middle", 800)
    text(158, y0 + 120, "HC-SR04", 11, "middle", 700, "#dbeafe")


def esp32():
    begin("esp32")
    x1, x2, y1, y2 = 690, 960, 120, 1210
    o.append(f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" rx="14" fill="#23272e" stroke="#0b0d10" stroke-width="2" filter="url(#shadow)"/>')
    cx = (x1 + x2) / 2
    o.append(f'<rect x="{cx - 70}" y="140" width="140" height="62" rx="4" fill="#15181d"/>')
    o.append(f'<path d="M{cx - 58} 192 v-38 h14 v30 h14 v-30 h14 v30 h14 v-30 h14 v30 h14 v-30 h14 v38" fill="none" stroke="#d4af37" stroke-width="3"/>')
    o.append(f'<rect x="{cx - 70}" y="205" width="140" height="170" rx="4" fill="url(#metal)" stroke="#8a929b" filter="url(#shadow)"/>')
    text(cx, 260, "ESP-WROOM-32", 16, "middle", 800, "#2b3036")
    text(cx, 284, "Wi-Fi + BT SoC", 12, "middle", 600, "#4b5563")
    o.append(f'<rect x="{cx - 20}" y="{y2 - 18}" width="40" height="30" rx="4" fill="url(#metal)" stroke="#7d858f"/>')
    for bx in (cx - 70, cx + 44):
        o.append(f'<rect x="{bx}" y="{y2 - 70}" width="26" height="22" rx="3" fill="#e5e7eb"/><circle cx="{bx + 13}" cy="{y2 - 59}" r="6" fill="#111"/>')
    text(cx, 700, "ESP32", 40, "middle", 800, "#f9fafb")
    text(cx, 740, "DevKit", 22, "middle", 600, "#9ca3af")
    end()


def pins(x, items, side):
    for name, y in items.items():
        begin(f"pin-{name.strip()}")
        o.append(f'<rect x="{x - 10 if side == "left" else x - 60}" y="{y - 14}" width="70" height="28" fill="transparent"/>')
        o.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#d4af37" stroke="#7a611d" stroke-width="2"/>')
        text(x + (18 if side == "left" else -18), y, name.strip(), 18, "start" if side == "left" else "end", 800, "#f9fafb")
        end()


def mosfet(x, gy):
    """IRLZ44N (TO-220), printed side facing you: legs G, D, S from left to right."""
    o.append(f'<rect x="{x}" y="{gy - 100}" width="90" height="48" rx="5" fill="url(#metal)" stroke="#7d858f" filter="url(#shadow)"/>')
    o.append(f'<circle cx="{x + 45}" cy="{gy - 78}" r="10" fill="#fff" stroke="#7d858f"/>')
    o.append(f'<rect x="{x - 3}" y="{gy - 55}" width="96" height="60" rx="4" fill="url(#black3d)" filter="url(#shadow)"/>')
    text(x + 45, gy - 33, "IRLZ44N", 14, "middle", 800, "#e5e7eb")
    for i, leg in enumerate("GDS"):
        lx = x + 15 + i * 30
        o.append(f'<rect x="{lx - 3}" y="{gy + 5}" width="6" height="45" fill="url(#metal)" stroke="#8a929b" stroke-width=".8"/>')
        text(lx, gy - 8, leg, 15, "middle", 900, "#fbbf24")
    return {leg: (x + 15 + i * 30, gy + 50) for i, leg in enumerate("GDS")}


def diode_v(x, y1, y2):
    """1N4007 standing up: black body, silver stripe at the top (cathode)."""
    wire([(x, y1), (x, y1 + 14)], "#9ca3af", 3); wire([(x, y2 - 14), (x, y2)], "#9ca3af", 3)
    o.append(f'<rect x="{x - 12}" y="{y1 + 12}" width="24" height="{y2 - y1 - 24}" rx="9" fill="url(#black3d)" filter="url(#shadow)"/>')
    o.append(f'<rect x="{x - 12}" y="{y1 + 18}" width="24" height="9" fill="url(#metal)"/>')


def coin_motor(x, y):
    o.append(f'<circle cx="{x}" cy="{y}" r="32" fill="url(#metal)" stroke="#7d858f" stroke-width="2" filter="url(#shadow)"/>')
    o.append(f'<circle cx="{x}" cy="{y}" r="22" fill="none" stroke="#9aa1aa" stroke-width="1.5"/>')
    text(x, y + 1, "3V", 13, "middle", 800, "#4b5563")


def mpu6050():
    x, y = 1250, 150
    begin("mpu")
    o.append(f'<rect x="{x}" y="{y}" width="230" height="230" rx="10" fill="#2342a0" stroke="#172a6b" stroke-width="2" filter="url(#shadow)"/>')
    for hx in (x + 205,):
        for hy in (y + 25, y + 205):
            o.append(f'<circle cx="{hx}" cy="{hy}" r="10" fill="#fff" stroke="#d4af37" stroke-width="3"/>')
    o.append(f'<rect x="{x + 120}" y="{y + 85}" width="52" height="52" rx="3" fill="#111317"/>')
    text(x + 146, y + 111, "MPU-6050", 9, "middle", 700, "#9ca3af")
    text(x + 146, y + 168, "GY-521", 16, "middle", 800, "#e0e7ff")
    o.append(f'<path d="M{x + 120} {y + 45} h34 m-8 -6 l8 6 l-8 6" fill="none" stroke="#e0e7ff" stroke-width="2"/>')
    text(x + 162, y + 45, "X", 12, "start", 800, "#e0e7ff")
    text(x + 115, y + 255, "MPU6050 (GY-521)", 19, "middle", 800)
    text(x + 20, y + 210, "XDA XCL AD0 INT:", 12, "start", 600, "#c7d2fe")
    text(x + 20, y + 226, "leave empty", 12, "start", 600, "#c7d2fe")
    end()


# ---------------------------------------------------------------- drawing
text(40, 40, "Belt for Blind · How to connect everything", 30, "start", 800)
text(40, 76, "Coloured tags with the same name are joined together:  5V = ESP32 VIN pin  ·  "
     "3V3 = ESP32 3V3 pin  ·  GND = any ESP32 GND pin", 17, "start", 500, MUTED)

esp32()
LEFT = {"VIN": 190, "GND": 240, "D25": 380, "D34": 410, "D26": 680, "D35": 710, "D27": 980, "D32": 1010}
RIGHT = {"3V3": 190, "GND ": 240, "D21": 290, "D22": 340, "D13": 630, "D33": 910, "D4": 1190}
begin("pin-VIN"); wire([(690, 190), (630, 190)], C["5V"]); end(); tag(630, 190, "5V", "right")
begin("pin-GND"); wire([(690, 240), (630, 240)], C["GND"]); end(); tag(630, 240, "GND", "right")

# Ultrasonic sensors
for name, y0, trig, echo in (("LEFT", 345, "D25", "D34"), ("CENTER", 645, "D26", "D35"), ("RIGHT", 945, "D27", "D32")):
    side = name.lower()
    begin(f"sensor-{side}")
    hcsr04(y0, name)
    rows = {"VCC": y0 + 5, "Trig": y0 + 35, "Echo": y0 + 65, "GND": y0 + 95}
    for pin, y in rows.items():
        o.append(f'<rect x="222" y="{y - 5}" width="16" height="10" fill="url(#metal)"/>')
        text(208, y, pin, 13, "end", 800, "#fff")
    wire([(238, rows["VCC"]), (262, rows["VCC"])], C["5V"])
    wire([(238, rows["GND"]), (262, rows["GND"])], C["GND"])
    wire([(238, rows["Trig"]), (690, rows["Trig"])], C["trig"])
    ye = rows["Echo"]
    wire([(238, ye), (350, ye)], C["echo"])
    wire([(440, ye), (690, ye)], C["echo"]); dot(540, ye, C["echo"])
    wire([(540, ye), (540, ye + 22)], C["echo"])
    text(590, rows["Trig"] - 15, f"Trig → {trig}", 14, "middle", 800, C["trig"])
    text(610, ye - 15, f"Echo → {echo}", 14, "middle", 800, C["echo"])
    end()
    tag(262, rows["VCC"], "5V")
    tag(262, rows["GND"], "GND")
    begin(f"r1k-{side}")
    resistor_h(350, 440, ye, ["brown", "black", "red", "gold"], "1kΩ")
    end()
    begin(f"r2k-{side}")
    resistor_v(540, ye + 22, ye + 100, ["red", "black", "red", "gold"], "2kΩ")
    wire([(540, ye + 100), (540, ye + 106)], C["GND"])
    end()
    tag(540, ye + 120, "GND", "center")
    if name == "LEFT":
        text(395, ye + 50, "brown-black-red", 12, "middle", 600, MUTED)
        text(564, ye + 75, "red-black-red", 12, "start", 600, MUTED)

pins(690, LEFT, "left")

# MPU6050
mpu6050()
for pin, y, esp, color in (("VCC", 190, "3V3", C["3V3"]), ("GND", 240, "GND", C["GND"]),
                           ("SDA", 290, "D21", C["sda"]), ("SCL", 340, "D22", C["scl"])):
    begin("mpu")
    o.append(f'<rect x="1236" y="{y - 5}" width="16" height="10" fill="url(#metal)"/>')
    text(1264, y, pin, 15, "start", 800, "#e0e7ff")
    wire([(960, y), (1236, y)], color)
    text(1100, y - 15, f"{esp} → {pin}", 14, "middle", 800, color)
    end()

# Vibration motors
text(1530, 455, "Vibration motors", 21, "start", 800)
text(1530, 481, "one per side", 15, "start", 600, MUTED)
for name, gy, pin in (("LEFT motor", 580, "D13"), ("CENTER motor", 860, "D33"), ("RIGHT motor", 1140, "D4")):
    side = name.split()[0].lower()
    begin(f"mosfet-{side}")
    legs = mosfet(1110, gy)
    gx, sy = legs["G"]
    dx, _ = legs["D"]
    sx, _ = legs["S"]
    # signal from the ESP32 pin to the Gate, and Source to GND
    wire([(960, sy), (gx, sy)], C["sig"]); dot(gx, sy, C["sig"])
    text(1035, sy - 15, f"{pin} → G", 14, "middle", 800, C["sig"])
    wire([(sx, sy), (sx, sy + 28), (sx + 38, sy + 28)], C["GND"])
    end()
    tag(sx + 38, sy + 28, "GND")
    # 10k from Gate to GND
    begin(f"r10k-{side}")
    wire([(gx, sy), (gx, sy + 12)], C["sig"], 3)
    resistor_v(gx, sy + 12, sy + 92, ["brown", "black", "orange", "gold"], "")
    text(gx - 22, sy + 52, "10kΩ", 15, "end", 800)
    end()
    tag(gx, sy + 110, "GND", "center")
    # motor: black to Drain, red to 3V3
    mx = 1350
    begin(f"motor-{side}")
    wire([(dx, sy), (dx, sy + 62), (mx, sy + 62), (mx, gy - 2)], C["black"]); dot(mx, sy + 62)
    coin_motor(mx, gy - 34)
    wire([(mx, gy - 66), (mx, gy - 118)], C["red"]); dot(mx, gy - 100, C["red"])
    text(mx - 14, gy - 82, "red", 13, "end", 700, C["red"])
    text(mx - 14, gy + 14, "black", 13, "end", 700, INK)
    text(1530, gy + 30, name, 20, "start", 800)
    text(1530, gy + 56, f"signal: {pin}", 15, "start", 600, MUTED)
    end()
    tag(mx, gy - 132, "3V3", "center")
    # diode across the motor, stripe to 3V3
    begin(f"diode-{side}")
    wire([(mx, gy - 100), (1440, gy - 100), (1440, gy - 82)], "#9ca3af", 3)
    diode_v(1440, gy - 82, gy + 30)
    wire([(1440, gy + 30), (1440, sy + 62), (mx, sy + 62)], "#9ca3af", 3)
    text(1462, gy - 40, "1N4007", 15, "start", 800)
    text(1462, gy - 20, "stripe ↑ to 3V3", 13, "start", 700, MUTED)
    end()

pins(960, RIGHT, "right")

# Parts guide
o.append('<rect x="40" y="1150" width="610" height="180" rx="12" fill="#f3f4f6"/>')
text(60, 1176, "Good to know", 19, "start", 800)
for i, g in enumerate([
    "IRLZ44N: hold it printed side facing you → legs G · D · S",
    "1N4007: the silver stripe end goes to 3V3 (motor's red wire)",
    "Motors run on 3V3, never 5V · sensors run on 5V (VIN)",
    "No 220Ω needed: D13 / D33 / D4 go straight to G",
    "Never let 5V or 3V3 touch GND (short circuit)",
]):
    text(60, 1206 + i * 25, "• " + g, 15, "start", 500)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'font-family="-apple-system, Helvetica, Arial, sans-serif">{DEFS}'
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>' + "".join(o) + "</svg>")
OUT.write_text(svg)
