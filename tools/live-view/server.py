#!/usr/bin/env python3
"""Live view for the Belt for Blind sensors.

Reads the ESP32's serial output and streams it to a web page at http://localhost:8000.
Run it with PlatformIO's Python, which already has pyserial:

    ~/.platformio/penv/bin/python tools/live-view/server.py

Only one program can use the USB port at a time, so close the Serial Monitor
first, and stop this server (Ctrl+C) before uploading new firmware.
"""
import argparse
import json
import mimetypes
import re
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

import serial
from serial.tools import list_ports

HERE = Path(__file__).parent
MODEL_DIR = HERE.parents[1] / "3d-model"
WIRING_IMAGE = HERE.parents[1] / "docs" / "wiring-pictorial.svg"  # made by tools/wiring/make_wiring_image.py

# USB-to-serial chips found on ESP32 boards: CH340, CP210x, FTDI, Espressif native USB
ESP32_USB_VIDS = {0x1A86, 0x10C4, 0x0403, 0x303A}

# Matches the per-sensor lines printed by src/main.cpp, e.g.
#   "  Left      28 cm   ##    VERY CLOSE"
#   "  Center    --      nothing in front"
#   "  Right   NO SIGNAL - check this sensor's wires"
SENSOR_LINE = re.compile(r"^\s+(Left|Center|Right)\s+(?:(\d+) cm|(--\s+nothing in front)|NO SIGNAL)")
#   "  Motor   ON  - Left (<15 cm) Center (<30 cm)"  /  "  Motor   off"
MOTOR_LINE = re.compile(r"^\s+Motor\s+(ON|off)(.*)")
#   "  IMU     tilt   3 deg   motion 0.012 g   gravity  0.01 -0.02  1.00"
#   "  IMU     NOT FOUND - belt stays on, check its wires"
IMU_LINE = re.compile(r"^\s+IMU\s+(?:tilt\s+(\d+) deg\s+motion ([\d.]+) g"
                      r"(?:\s+gravity\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+))?|NOT FOUND)")
#   "--- wearer is sitting: sensors and motors paused ---"  /  "--- wearer is up: belt back on ---"
SITTING_LINE = re.compile(r"^--- wearer is (sitting|up)")
SENSOR_NAMES = ("Left", "Center", "Right")


class LiveState:
    """Latest readings, shared between the serial thread and the web clients."""

    def __init__(self):
        self.cond = threading.Condition()
        self.version = 0
        self.snapshot = {
            "connected": False, "port": None, "error": None, "updated": None,
            "sensors": {}, "motors": {}, "imu": None, "sitting": False,
        }

    def update(self, **changes):
        with self.cond:
            self.snapshot = {**self.snapshot, **changes}
            self.version += 1
            self.cond.notify_all()

    def wait_for_change(self, seen_version, timeout):
        with self.cond:
            self.cond.wait_for(lambda: self.version != seen_version, timeout)
            return self.version, self.snapshot


def find_esp32_port():
    for p in list_ports.comports():
        if p.vid in ESP32_USB_VIDS:
            return p.device
    return None


def parse_line(line, sensors):
    """Returns the snapshot fields this line of firmware output changes, or None."""
    m = SENSOR_LINE.match(line)
    if m:
        name, cm, nothing = m.groups()
        if cm is not None:
            reading = {"status": "ok", "cm": int(cm)}
        elif nothing is not None:
            reading = {"status": "clear"}
        else:
            reading = {"status": "nosignal"}
        return {"sensors": {**sensors, name: reading}, "sitting": False}
    m = MOTOR_LINE.match(line)
    if m:
        on, which = m.group(1) == "ON", m.group(2)
        return {"motors": {name: on and name in which for name in SENSOR_NAMES}}
    m = IMU_LINE.match(line)
    if m:
        tilt, motion, *gravity = m.groups()
        found = tilt is not None
        return {"imu": {
            "found": found,
            "tilt": int(tilt) if found else None,
            "motion": float(motion) if found else None,
            "gravity": [float(g) for g in gravity] if gravity[0] is not None else None,
        }}
    m = SITTING_LINE.match(line)
    if m:
        return {"sitting": m.group(1) == "sitting"}
    return None


def read_serial_forever(state, port_arg, baud):
    while True:
        port = port_arg or find_esp32_port()
        if not port:
            state.update(connected=False, port=None, error="ESP32 not found - is the USB cable plugged in?")
            time.sleep(2)
            continue

        ser = serial.Serial()
        ser.port, ser.baudrate, ser.timeout = port, baud, 1
        ser.dtr = ser.rts = False  # don't reset the board when opening the port
        try:
            ser.open()
        except serial.SerialException:
            state.update(connected=False, port=port, error=f"{port} is busy - close the Serial Monitor")
            time.sleep(2)
            continue

        state.update(connected=True, port=port, error=None)
        try:
            with ser:
                while True:
                    changes = parse_line(ser.readline().decode(errors="replace"), state.snapshot["sensors"])
                    if changes:
                        state.update(**changes, updated=time.time())
        except (serial.SerialException, OSError):
            state.update(connected=False, error=f"Lost connection to {port} - was the USB cable unplugged?")
            time.sleep(1)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path in ("/dashboard", "/dashboard/", "/index.html"):
                self.send_file(HERE / "index.html", "text/html; charset=utf-8")
            elif path == "/events":
                self.stream_events()
            elif path in ("/", "/3d", "/3d/", "/3d.html"):  # the 3D workspace with wiring is the home page
                self.send_file(HERE / "3d.html", "text/html; charset=utf-8")
            elif path == "/wiring.svg":
                self.send_file(WIRING_IMAGE, "image/svg+xml")
            elif path == "/assets/workshop.hdr":
                self.send_file(MODEL_DIR / "hdri/artist_workshop_4k.hdr", "application/octet-stream")
            elif path in ("/3d.js", "/3d.css", "/orientation.js", "/live-state.js", "/wiring.js") or path.startswith(("/assets/", "/vendor/")):
                file = (HERE / path.lstrip("/")).resolve()
                if not file.is_relative_to(HERE.resolve()) or ".." in Path(path).parts:
                    self.send_error(404)
                    return
                content_type = "text/javascript; charset=utf-8" if file.suffix == ".js" else mimetypes.guess_type(file)[0] or "application/octet-stream"
                self.send_file(file, content_type)
            else:
                self.send_error(404)

        def send_file(self, path, content_type):
            if not path.is_file():
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(path.stat().st_size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                with path.open("rb") as body:
                    shutil.copyfileobj(body, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def stream_events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            version = -1
            try:
                while True:
                    # Times out every second so the page also gets a heartbeat
                    version, snap = state.wait_for_change(version, timeout=1.0)
                    age = time.time() - snap["updated"] if snap["updated"] else None
                    self.wfile.write(f"data: {json.dumps({**snap, 'age': age})}\n\n".encode())
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass  # keep the terminal quiet

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (default: auto-detect the ESP32)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--http-port", type=int, default=8000)
    args = parser.parse_args()

    state = LiveState()
    threading.Thread(target=read_serial_forever, args=(state, args.port, args.baud), daemon=True).start()

    server = ThreadingHTTPServer(("127.0.0.1", args.http_port), make_handler(state))
    print(f"Live view running: open http://localhost:{args.http_port}  (Ctrl+C to stop)")
    print(f"Live 3D model: http://localhost:{args.http_port}/3d")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
