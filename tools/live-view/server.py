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
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
from serial.tools import list_ports

HERE = Path(__file__).parent

# USB-to-serial chips found on ESP32 boards: CH340, CP210x, FTDI, Espressif native USB
ESP32_USB_VIDS = {0x1A86, 0x10C4, 0x0403, 0x303A}

# Matches the per-sensor lines printed by src/main.cpp, e.g.
#   "  Left      28 cm   ##    VERY CLOSE"
#   "  Center    --      nothing in front"
#   "  Right   NO SIGNAL - check this sensor's wires"
SENSOR_LINE = re.compile(r"^\s+(Left|Center|Right)\s+(?:(\d+) cm|(--\s+nothing in front)|NO SIGNAL)")
#   "  Buzzer  ON  - something closer than 15 cm!"  /  "  Buzzer  off"
BUZZER_LINE = re.compile(r"^\s+Buzzer\s+(ON|off)")


class LiveState:
    """Latest readings, shared between the serial thread and the web clients."""

    def __init__(self):
        self.cond = threading.Condition()
        self.version = 0
        self.snapshot = {
            "connected": False, "port": None, "error": None, "sensors": {}, "buzzer": None, "updated": None,
        }

    def update(self, **changes):
        with self.cond:
            self.snapshot = {**self.snapshot, **changes}
            self.version += 1
            self.cond.notify_all()

    def set_sensor(self, name, reading):
        with self.cond:
            sensors = {**self.snapshot["sensors"], name: reading}
        self.update(sensors=sensors, updated=time.time())

    def wait_for_change(self, seen_version, timeout):
        with self.cond:
            self.cond.wait_for(lambda: self.version != seen_version, timeout)
            return self.version, self.snapshot


def find_esp32_port():
    for p in list_ports.comports():
        if p.vid in ESP32_USB_VIDS:
            return p.device
    return None


def parse_line(line):
    m = SENSOR_LINE.match(line)
    if not m:
        return None
    name, cm, nothing = m.groups()
    if cm is not None:
        return name, {"status": "ok", "cm": int(cm)}
    if nothing is not None:
        return name, {"status": "clear"}
    return name, {"status": "nosignal"}


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
                    line = ser.readline().decode(errors="replace")
                    parsed = parse_line(line)
                    buzzer = BUZZER_LINE.match(line)
                    if parsed:
                        state.set_sensor(*parsed)
                    elif buzzer:
                        state.update(buzzer=buzzer.group(1) == "ON", updated=time.time())
        except (serial.SerialException, OSError):
            state.update(connected=False, error=f"Lost connection to {port} - was the USB cable unplugged?")
            time.sleep(1)


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_file(HERE / "index.html", "text/html; charset=utf-8")
            elif self.path == "/events":
                self.stream_events()
            else:
                self.send_error(404)

        def send_file(self, path, content_type):
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

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
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
