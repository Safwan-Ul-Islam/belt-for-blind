"""Live link: the Blender model follows the real sensors.

Uses the same live data as the web page, so tools/live-view/server.py must be
running (it is whenever http://localhost:8000 works). In Blender's Scripting tab,
click Run Script to start; click it again to stop.

Each sensor's beam stretches to the measured distance (to scale, up to 2 m),
coloured like the web page, with the distance floating above the sensor.
Each vibration motor glows and sends out rings while it vibrates. The IMU's
tilt and motion float above the MPU6050, and everything pauses while the
wearer sits.

The whole model also tilts the way the real breadboard tilts, using the
MPU6050's gravity reading. Start the link with the breadboard flat and still:
that position counts as level. Turning it flat on the table (around the
vertical axis) can't be seen by an accelerometer, so only tilts are shown.
"""
import json
import math
import threading
import time
import urllib.request

import bpy
from mathutils import Matrix, Quaternion, Vector

URL = "http://localhost:8000/events"
KEY = "belt_live_link"

# Vibrate distance per sensor, as in src/main.cpp; each sensor has its own motor
ALERT_CM = {"Left": 15, "Center": 30, "Right": 15}
STILL_MOTION_G = 0.03
WALK_MOTION_G = 0.08
MAX_CM = 200      # longest beam drawn
CLEAR_CM = 30     # faint beam length when nothing is in front
STALE_AFTER_S = 3

ROOT = "Belt for Blind (mm)"
# The sensor axis pointing up when the link starts is taken as up. If tilting the real breadboard
# forward makes the model tilt sideways or backward, change this to 90, 180 or 270.
TURN_SENSOR_DEG = 0


def linear(hex_color):
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


# Same colours as the web page
COLORS = {
    "too-close": linear("#e5484d"),
    "very-close": linear("#ea6a12"),
    "close": linear("#facc15"),
    "far": linear("#34c26f"),
    "clear": linear("#5aa9ff"),
    "nosignal": linear("#8b95a3"),
}
MOTOR_RED = linear("#ff2a2a")


def zone_of(cm):
    if cm < 15:
        return "too-close"
    if cm < 50:
        return "very-close"
    if cm < 150:
        return "close"
    return "far"


_last_colors = {}


def set_color(material, rgb, alpha=None, emission=None):
    # Only touch the material when something changed, so the Rendered view can settle
    value = (tuple(round(c, 4) for c in rgb), alpha and round(alpha, 3), emission and round(emission, 2))
    if _last_colors.get(material.name) == value:
        return
    _last_colors[material.name] = value
    bsdf = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
    if emission is not None:
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha is not None:
        bsdf.inputs["Alpha"].default_value = alpha
    material.diffuse_color = (*rgb, 1 if alpha is None else alpha)


def set_hidden(obj, hidden):
    if obj.hide_viewport != hidden:
        obj.hide_viewport = hidden


def find_layer_collection(layer, name):
    if layer.name == name:
        return layer
    for child in layer.children:
        found = find_layer_collection(child, name)
        if found:
            return found
    return None


def static_beams():
    return find_layer_collection(bpy.context.view_layer.layer_collection, "Sound beams")


def show_static_beams(visible):
    lc = static_beams()
    if lc:
        lc.hide_viewport = not visible


def live_objects():
    names = [f"Live beam {s}" for s in ALERT_CM] + [f"Live distance {s}" for s in ALERT_CM]
    names += [f"Live motor ring {s} {k}" for s in ALERT_CM for k in range(3)] + ["Live status", "Live IMU"]
    return [o for o in (bpy.data.objects.get(n) for n in names) if o]


def read_events(state):
    """Background thread: keeps the latest snapshot from the live-view server."""
    while not state["stop"].is_set():
        try:
            with urllib.request.urlopen(URL, timeout=5) as resp:
                state["error"] = None
                for raw in resp:
                    if state["stop"].is_set():
                        return
                    line = raw.decode("utf-8", "replace").strip()
                    if line.startswith("data: "):
                        state["snap"] = json.loads(line[6:])
                        state["received"] = time.time()
        except Exception as exc:  # server not running yet, or stopped
            state["error"] = exc
            state["snap"] = None
            state["stop"].wait(1.0)


def update_sensor(state, name, reading, now):
    beam = bpy.data.objects[f"Live beam {name}"]
    label = bpy.data.objects[f"Live distance {name}"]
    side = bpy.data.materials[f"Live beam {name}"]
    cap = bpy.data.materials[f"Live obstacle {name}"]
    text_mat = bpy.data.materials[f"Live text {name}"]

    status = reading["status"] if reading else "waiting"
    alert = False
    if status == "ok":
        cm = reading["cm"]
        zone, target, body = zone_of(cm), min(cm, MAX_CM) * 10, f"{cm} cm"
        alert = cm < ALERT_CM[name]
    elif status == "clear":
        zone, target, body = "clear", CLEAR_CM * 10, "clear"
    else:
        zone, target = "nosignal", None
        body = {"nosignal": "no signal", "paused": "paused"}.get(status, "--")

    # Beam length in mm, easing toward the newest reading
    cur = state["lengths"].get(name)
    if target is None:
        set_hidden(beam, True)
        state["lengths"][name] = None
    else:
        settled = cur is not None and abs(target - cur) < 0.5
        if not settled:
            cur = target if cur is None or abs(target - cur) < 1 else cur + (target - cur) * 0.3
            state["lengths"][name] = cur
            beam.scale = (cur, cur, cur)
        set_hidden(beam, False)

    pulse = 0.5 + 0.5 * math.sin(now * 12)
    rgb = COLORS[zone]
    if alert:  # this sensor is making its motor vibrate: flash
        set_color(side, rgb, alpha=0.2 + 0.35 * pulse, emission=0.8)
        set_color(cap, rgb, alpha=0.95, emission=0.6 + 1.6 * pulse)
    elif zone == "clear":
        set_color(side, rgb, alpha=0.1, emission=0.5)
        set_color(cap, rgb, alpha=0.1, emission=0.5)
    else:
        set_color(side, rgb, alpha=0.22, emission=0.5)
        set_color(cap, rgb, alpha=0.9, emission=0.8)

    if label.data.body != body:
        label.data.body = body
    set_color(text_mat, rgb, emission=0.5)
    set_hidden(label, False)


def update_motor(state, name, on, now):
    top = bpy.data.materials[f"Motor top {name}"]
    if on:
        set_color(top, MOTOR_RED, emission=0.8 + 1.6 * (0.5 + 0.5 * math.sin(now * 20)))
    else:
        set_color(top, state["motor_rgb"][name], emission=0.0)
    for k in range(3):
        ring = bpy.data.objects[f"Live motor ring {name} {k}"]
        set_hidden(ring, not on)
        if on:
            s = 1 + 2.2 * ((now * 2.2 + k / 3) % 1)
            ring.scale = (s, s, 1)


def sensor_to_model(level):
    """Rotation from the sensor's axes to the model's: the axis that is up at the start maps to up."""
    k = max(range(3), key=lambda a: abs(level[a]))
    sign = 1 if level[k] > 0 else -1
    i, j = (k + 1) % 3, (k + 2) % 3
    columns = [None] * 3  # where each sensor axis points in the model
    columns[k], columns[i], columns[j] = Vector((0, 0, sign)), Vector((1, 0, 0)), Vector((0, sign, 0))
    return Matrix.Rotation(math.radians(TURN_SENSOR_DEG), 3, "Z") @ Matrix(columns).transposed()


def update_tilt(state, imu):
    """Turn the model so it leans the way the real breadboard leans."""
    gravity = imu and imu.get("gravity")
    if not gravity or Vector(gravity).length < 0.5:
        return
    gravity = Vector(gravity).normalized()
    if state["level"] is None:
        state["level"] = gravity
        state["sensor_to_model"] = sensor_to_model(gravity)
    m = state["sensor_to_model"]
    target = (m @ gravity).rotation_difference(m @ state["level"])
    root = bpy.data.objects[ROOT]
    current = root.rotation_quaternion.copy()
    eased = current.slerp(target, 0.25)
    if current.rotation_difference(eased).angle > math.radians(0.05):
        root.rotation_quaternion = eased


def update_imu(imu, sitting):
    label = bpy.data.objects["Live IMU"]
    if imu is None:
        body, color = "IMU --", COLORS["nosignal"]
    elif not imu["found"]:
        body, color = "IMU not found", COLORS["very-close"]
    elif sitting:
        body, color = f"Sitting, paused · tilt {imu['tilt']}°", COLORS["nosignal"]
    else:
        moving = "moving" if imu["motion"] >= WALK_MOTION_G else "moving a little" if imu["motion"] >= STILL_MOTION_G else "still"
        body, color = f"Tilt {imu['tilt']}° · {moving}", COLORS["far"] if moving == "moving" else COLORS["clear"]
    if label.data.body != body:
        label.data.body = body
    set_color(bpy.data.materials["Live IMU text"], color, emission=0.5)
    set_hidden(label, False)


def tick():
    state = bpy.app.driver_namespace.get(KEY)
    if state is None or state["stop"].is_set():
        return None  # stops the timer
    now = time.time()
    snap = state["snap"]
    live = (snap is not None and snap.get("connected") and snap.get("age") is not None
            and snap["age"] < STALE_AFTER_S and now - state["received"] < STALE_AFTER_S)

    sitting = bool(live and snap.get("sitting"))
    for name in ALERT_CM:
        reading = {"status": "paused"} if sitting else snap["sensors"].get(name) if live else None
        update_sensor(state, name, reading, now)
        update_motor(state, name, bool(live and not sitting and snap.get("motors", {}).get(name)), now)
    update_imu(snap.get("imu") if live else None, sitting)
    if live:
        update_tilt(state, snap.get("imu"))

    status = bpy.data.objects["Live status"]
    if sitting:
        body = "PAUSED: wearer is sitting"
    elif live:
        body = "LIVE"
    elif state["error"] is not None:
        body = "Start the live-view server (see README)"
    elif snap is not None and not snap.get("connected"):
        body = snap.get("error") or "Waiting for the ESP32..."
    else:
        body = "Waiting for readings..."
    if status.data.body != body:
        status.data.body = body
    set_hidden(status, False)

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 0.05


def start():
    missing = [f"Live beam {s}" for s in ALERT_CM if f"Live beam {s}" not in bpy.data.objects]
    if missing:
        raise RuntimeError("This file has no live objects; rebuild it with build_model.py")
    motor_rgb = {}
    for name in ALERT_CM:
        bsdf = next(n for n in bpy.data.materials[f"Motor top {name}"].node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        motor_rgb[name] = tuple(bsdf.inputs["Base Color"].default_value[:3])
    state = {
        "stop": threading.Event(), "snap": None, "error": None, "received": 0.0, "lengths": {},
        "motor_rgb": motor_rgb, "level": None,
    }
    root = bpy.data.objects[ROOT]
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = Quaternion()
    bpy.app.driver_namespace[KEY] = state
    threading.Thread(target=read_events, args=(state,), daemon=True).start()
    state["beams_were_visible"] = bool(static_beams() and not static_beams().hide_viewport)
    show_static_beams(False)
    bpy.app.timers.register(tick)
    state["tick"] = tick
    print("Live link started: the model now follows the sensors. Run the script again to stop.")


def stop(state):
    state["stop"].set()
    for o in live_objects():
        o.hide_viewport = True
    for name, rgb in state["motor_rgb"].items():
        set_color(bpy.data.materials[f"Motor top {name}"], rgb, emission=0.0)
    show_static_beams(state.get("beams_were_visible", False))
    root = bpy.data.objects[ROOT]
    root.rotation_quaternion = Quaternion()
    root.rotation_mode = "XYZ"
    print("Live link stopped.")


running = bpy.app.driver_namespace.get(KEY)
running_tick = running.get("tick") if running else None
if running_tick and bpy.app.timers.is_registered(running_tick):
    stop(running)
else:
    if running:
        running["stop"].set()  # left over from before the file was reloaded
    start()
