"""Belt for Blind - 3D model of the breadboard prototype.

Builds the hardware as it sits on the desk: an ESP32 DevKit plugged into a
half-size breadboard, three HC-SR04 sensors on jumper wires (left, front,
right), the 1k/2k divider on each Echo line and the TMB12A05 buzzer on D13.
Wiring matches src/main.cpp and the README.

Run with Blender (no window needed):
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        -P build_model.py -- belt_for_blind.blend [preview.png]

All geometry is in millimetres under one root empty scaled to metres.
The file also carries live_link.py (Scripting tab), which makes the model follow
the real sensors through the live-view server.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

PITCH = 2.54  # breadboard / header hole spacing, mm

# ---------------------------------------------------------------- breadboard layout
BB_SIZE = (83.5, 54.5, 8.5)
BB_TOP = BB_SIZE[2]
ROWS = {"a": 13.97, "b": 11.43, "c": 8.89, "d": 6.35, "e": 3.81,
        "f": -3.81, "g": -6.35, "h": -8.89, "i": -11.43, "j": -13.97}
RAILS = {"top+": 21.59, "top-": 19.05, "bot-": -19.05, "bot+": -21.59}


def col_x(col):
    return (col - 15.5) * PITCH


def hole(col, row):
    return Vector((col_x(col), ROWS.get(row, RAILS.get(row)), BB_TOP))


# ESP32 pins sit in rows b (VIN side) and j, columns 2 (VIN) to 16 (EN)
ESP_POS = Vector((col_x(9), (ROWS["b"] + ROWS["j"]) / 2, BB_TOP + 2.5))
ESP_VIN_SIDE = ["EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26", "D27", "D14", "D12", "D13", "GND", "VIN"]
ESP_3V3_SIDE = ["D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5", "TX2", "RX2", "D4", "D2", "D15", "GND", "3V3"]


def esp_col(pin):
    return 16 - ESP_VIN_SIDE.index(pin)


# Sensors: name, position on the desk, facing angle (0 = forward, +y), breadboard holes for VCC/Trig/Echo/Gnd
SENSORS = [
    ("Left",   (-125, 12), 90,  {"VCC": ("top+", 5),  "Trig": ("a", esp_col("D25")), "Echo": ("e", 20), "Gnd": ("top-", 6)}),
    ("Center", (0, 125),   0,   {"VCC": ("top+", 14), "Trig": ("a", esp_col("D26")), "Echo": ("e", 25), "Gnd": ("top-", 15)}),
    ("Right",  (125, 12),  -90, {"VCC": ("top+", 21), "Trig": ("a", esp_col("D27")), "Echo": ("j", 21), "Gnd": ("top-", 22)}),
]
# Echo divider per sensor: 1k from the Echo column to the meeting column, 2k from there to GND,
# and a jumper from the meeting column to the ESP32 pin
DIVIDERS = [
    {"r1k": ((20, "c"), (24, "c")), "r2k": ((24, "a"), (24, "top-")), "jumper": ((24, "e"), "D34")},
    {"r1k": ((25, "d"), (29, "d")), "r2k": ((29, "a"), (29, "top-")), "jumper": ((29, "e"), "D35")},
    {"r1k": ((21, "h"), (25, "h")), "r2k": ((25, "j"), (25, "bot-")), "jumper": ((25, "f"), "D32")},
]
BUZZER_PLUS, BUZZER_MINUS = (27, "g"), (30, "g")

# ---------------------------------------------------------------- scene helpers
COLLECTIONS = {}
MATS = {}


def collection(name):
    if name not in COLLECTIONS:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
        COLLECTIONS[name] = c
    return COLLECTIONS[name]


def linear(hex_color):
    h = hex_color.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def mat(name, hex_color, metallic=0.0, roughness=0.5, emission=0.0, alpha=1.0,
        coat=0.0, subsurface=0.0, bump=0.0, bump_scale=1.0, pattern="noise", stretch=(1, 1, 1)):
    """Principled material. coat = clear lacquer (solder mask, PVC), subsurface = light through
    plastic, bump = surface texture from a noise or checker pattern (scale per mm, stretch for brushed metal)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    rgba = (*linear(hex_color), 1.0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1:
        bsdf.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    if subsurface:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
        bsdf.inputs["Subsurface Scale"].default_value = 0.0008  # ~1 mm, the scene is in metres
    if bump:
        coord = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = stretch
        tex = nodes.new("ShaderNodeTexChecker" if pattern == "checker" else "ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = bump_scale
        bump_node = nodes.new("ShaderNodeBump")
        bump_node.inputs["Strength"].default_value = bump
        bump_node.inputs["Distance"].default_value = 0.0003
        links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        links.new(tex.outputs["Fac"], bump_node.inputs["Height"])
        links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = (*rgba[:3], alpha)  # colour in Solid view
    m.metallic, m.roughness = metallic, roughness
    MATS[name] = m
    return m


def wood_material():
    """Procedural oak for the optional desk."""
    m = bpy.data.materials.new("Desk wood")
    if m.node_tree is None:
        m.use_nodes = True
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Coat Weight"].default_value = 0.3
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.004, 0.06, 0.06)  # grain runs along x
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8.0
    wave = nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = 2.0
    wave.inputs["Distortion"].default_value = 6.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*linear("#7a4a26"), 1)
    ramp.color_ramp.elements[1].color = (*linear("#c48a52"), 1)
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Color"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (*linear("#a06a3c"), 1)
    return m


def add_obj(name, data, material, parent, coll, loc=(0, 0, 0), rot=(0, 0, 0)):
    o = bpy.data.objects.new(name, data)
    collection(coll).objects.link(o)
    if material is not None:
        o.data.materials.append(material)
    o.parent = parent
    o.location, o.rotation_euler = loc, rot
    return o


def group(name, parent, loc=(0, 0, 0), rot=(0, 0, 0), coll="Electronics"):
    e = add_obj(name, None, None, parent, coll, loc, rot)
    e.empty_display_type, e.empty_display_size = "PLAIN_AXES", 1
    return e


def bm_box(bm, size, center, rot=None):
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.LocRotScale(Vector(center), rot, Vector(size)))


def bm_cyl(bm, radius, length, center, axis=(0, 0, 1), radius_end=None, segments=24):
    axis = Vector(axis).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(axis)
    made = bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=segments,
        radius1=radius, radius2=radius if radius_end is None else radius_end, depth=length,
        matrix=Matrix.LocRotScale(Vector(center), rot, None))
    bm.normal_update()
    faces = {f for v in made["verts"] for f in v.link_faces}
    for f in faces:
        f.smooth = abs(f.normal.dot(axis)) < 0.7  # smooth sides, flat caps
    for f in faces:
        for e in f.edges:
            if len(e.link_faces) == 2 and e.link_faces[0].smooth != e.link_faces[1].smooth:
                e.smooth = False


def obj_from_bm(name, bm, material, parent, coll="Electronics", loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0):
    """material: one material, or a list matching the faces' material_index."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    extra = []
    if isinstance(material, list):
        material, *extra = material
    o = add_obj(name, me, material, parent, coll, loc, rot)
    for m in extra:
        o.data.materials.append(m)
    if bevel:
        b = o.modifiers.new("Bevel", "BEVEL")
        b.width, b.segments = bevel, 2
    return o


def box(name, size, center, material, parent, coll="Electronics", bevel=0.0):
    bm = bmesh.new()
    bm_box(bm, size, center)
    return obj_from_bm(name, bm, material, parent, coll, bevel=bevel)


def text(name, body, size, loc, material, parent, rot=(0, 0, 0), coll="Electronics"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size = body, size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    return add_obj(name, cu, material, parent, coll, loc, rot)


def wire(name, points, material, parent, radius=0.6, smooth=True, coll="Wires", handles=None):
    """handles: {point index: (left direction, right direction)} to override the automatic
    handles, e.g. to keep a wire flat on the desk instead of sagging through it."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth, cu.bevel_resolution, cu.use_fill_caps = radius, 3, True
    cu.resolution_u = 20
    if smooth:
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(points) - 1)
        for bp, p in zip(sp.bezier_points, points):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        for i, (left, right) in (handles or {}).items():
            p = Vector(points[i])
            reach = 0.35 * min((p - Vector(points[i - 1])).length, (Vector(points[i + 1]) - p).length)
            bp = sp.bezier_points[i]
            bp.handle_left_type = bp.handle_right_type = "FREE"
            bp.handle_left = p - Vector(left).normalized() * reach
            bp.handle_right = p + Vector(right).normalized() * reach
    else:
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for pt, p in zip(sp.points, points):
            pt.co = (*p, 1.0)
    return add_obj(name, cu, material, parent, coll)


# Text standing on a part's front face (+y), readable from the front
FRONT_TEXT = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0))).to_euler()


# ---------------------------------------------------------------- materials
def make_materials():
    return {
        "breadboard": mat("Breadboard plastic", "#f3f1ea", roughness=0.42, subsurface=0.2, bump=0.05, bump_scale=2),
        "hole": mat("Breadboard hole", "#141414", roughness=0.9),
        "channel": mat("Breadboard channel", "#c9c4b9", roughness=0.7),
        "rail_red": mat("Rail line red", "#d62828", roughness=0.5),
        "rail_blue": mat("Rail line blue", "#2463d6", roughness=0.5),
        "print_grey": mat("Breadboard print", "#8a877f", roughness=0.6),
        "pcb_black": mat("ESP32 PCB", "#23272e", roughness=0.5, coat=0.15, bump=0.03, bump_scale=1.5),
        "module": mat("Module PCB", "#181b20", roughness=0.5, coat=0.15),
        "shield": mat("Metal shield", "#c9ced4", metallic=1.0, roughness=0.3, bump=0.12, bump_scale=6, stretch=(0.05, 3, 3)),
        "gold": mat("Gold", "#d6b04c", metallic=1.0, roughness=0.18),
        "solder": mat("Solder", "#b8bcc2", metallic=1.0, roughness=0.15),
        "plastic_black": mat("Black plastic", "#141414", roughness=0.55, bump=0.08, bump_scale=3),
        "chip": mat("Chip", "#18191b", roughness=0.5, bump=0.05, bump_scale=4),
        "silk": mat("Silkscreen", "#f2f4f7", roughness=0.6),
        "dark_print": mat("Shield print", "#2b3036", roughness=0.6),
        "passive": mat("SMD part", "#b89b6e", roughness=0.5),
        "button": mat("Button base", "#d4d6d9", metallic=0.6, roughness=0.35),
        "led_red": mat("LED red", "#ff3b3b", emission=4.0),
        "led_blue": mat("LED blue", "#3b7bff", emission=4.0),
        "pcb_blue": mat("HC-SR04 PCB", "#1e5fb0", roughness=0.45, coat=0.15, bump=0.03, bump_scale=1.5),
        "can": mat("Transducer can", "#d9dde2", metallic=1.0, roughness=0.32, bump=0.08, bump_scale=4),
        "mesh": mat("Transducer mesh", "#26282c", roughness=0.95, bump=0.6, bump_scale=2.5, pattern="checker"),
        "buzzer": mat("Buzzer body", "#121212", roughness=0.3, coat=0.4),
        "resistor": mat("Resistor body", "#d9c49b", roughness=0.45, coat=0.5),
        "lead": mat("Resistor lead", "#c3c7cc", metallic=1.0, roughness=0.25),
        "band_brown": mat("Band brown", "#6b3a1e", roughness=0.45, coat=0.5),
        "band_black": mat("Band black", "#111111", roughness=0.45, coat=0.5),
        "band_red": mat("Band red", "#c0262d", roughness=0.45, coat=0.5),
        "band_gold": mat("Band gold", "#c9a14a", metallic=1.0, roughness=0.35),
        "wire_red": mat("Wire red", "#d62828", roughness=0.35, coat=0.25),
        "wire_black": mat("Wire black", "#222222", roughness=0.35, coat=0.25),
        "wire_yellow": mat("Wire yellow", "#f2c014", roughness=0.35, coat=0.25),
        "wire_blue": mat("Wire blue", "#2f6fe0", roughness=0.35, coat=0.25),
        "wire_pink": mat("Wire pink", "#ff5fa2", roughness=0.35, coat=0.25),
        "beam": mat("Sound beam", "#5aa9ff", emission=0.6, alpha=0.12),
        "label": mat("Label", "#3a3d42", roughness=0.7),
    }


WIRE_COLOR = {"VCC": "wire_red", "Gnd": "wire_black", "Trig": "wire_yellow", "Echo": "wire_blue"}


# ---------------------------------------------------------------- parts
def build_breadboard(M, root):
    g = group("Breadboard", root, coll="Breadboard")
    box("Breadboard body", BB_SIZE, (0, 0, BB_TOP / 2), M["breadboard"], g, coll="Breadboard", bevel=0.8)
    box("Centre channel", (80, 2.2, 0.06), (0, 0, BB_TOP + 0.01), M["channel"], g, coll="Breadboard")

    bm = bmesh.new()
    for col in range(1, 31):
        for y in list(ROWS.values()) + list(RAILS.values()):
            bm_box(bm, (1.0, 1.0, 0.06), (col_x(col), y, BB_TOP + 0.02))
    obj_from_bm("Holes", bm, M["hole"], g, coll="Breadboard")

    for name, y, m in (("+ line top", 23.6, "rail_red"), ("- line top", 17.2, "rail_blue"),
                       ("- line bottom", -17.2, "rail_blue"), ("+ line bottom", -23.6, "rail_red")):
        box(name, (78, 0.5, 0.06), (0, y, BB_TOP + 0.01), M[m], g, coll="Breadboard")
    for x in (-40.0, 40.0):
        text("+ top", "+", 2.2, (x, RAILS["top+"], BB_TOP + 0.02), M["rail_red"], g, coll="Breadboard")
        text("- top", "-", 2.2, (x, RAILS["top-"], BB_TOP + 0.02), M["rail_blue"], g, coll="Breadboard")
        text("- bottom", "-", 2.2, (x, RAILS["bot-"], BB_TOP + 0.02), M["rail_blue"], g, coll="Breadboard")
        text("+ bottom", "+", 2.2, (x, RAILS["bot+"], BB_TOP + 0.02), M["rail_red"], g, coll="Breadboard")
        for row, y in ROWS.items():
            text(f"row {row}", row, 1.3, (x * 0.99, y, BB_TOP + 0.02), M["print_grey"], g, coll="Breadboard")
    for col in (1, 5, 10, 15, 20, 25, 30):
        for y in (15.7, -15.7):
            text(f"col {col}", str(col), 1.2, (col_x(col), y, BB_TOP + 0.02), M["print_grey"], g, coll="Breadboard")


def build_esp32(M, root):
    g = group("ESP32", root, loc=ESP_POS)
    T = 1.6
    box("ESP32 PCB", (51.5, 28.0, T), (0, 0, T / 2), M["pcb_black"], g, bevel=0.4)

    # ESP-WROOM-32 module: PCB, metal shield, PCB antenna at the +x end
    box("WROOM-32 PCB", (25.5, 18, 0.8), (13.0, 0, T + 0.4), M["module"], g)
    box("WROOM-32 shield", (17.6, 16, 2.4), (9.55, 0, T + 2.0), M["shield"], g, bevel=0.3)
    bm = bmesh.new()
    xs = [19.6, 21.0, 22.4, 23.8, 25.2]
    for k, x in enumerate(xs):
        bm_box(bm, (0.45, 7, 0.05), (x, 0, T + 0.83))
        if k < len(xs) - 1:
            bm_box(bm, (1.85, 0.45, 0.05), (x + 0.7, 3.3 if k % 2 == 0 else -3.3, T + 0.83))
    obj_from_bm("Antenna trace", bm, M["gold"], g)
    top = T + 3.21
    for body, size, y in (("ESP-WROOM-32", 1.7, 3.6), ("Wi-Fi + BT SoC", 1.05, 0.9),
                          ("ISM 2.4GHz", 1.05, -0.9), ("802.11 b/g/n", 1.05, -2.7)):
        text(f"Shield: {body}", body, size, (9.55, y, top), M["dark_print"], g)

    # Pin headers: plastic strip under the board, pin tips + solder on top, labels
    bm_pins, bm_solder, bm_strip = bmesh.new(), bmesh.new(), bmesh.new()
    for y, names in ((12.7, ESP_VIN_SIDE), (-12.7, ESP_3V3_SIDE)):
        bm_box(bm_strip, (38.1, 2.5, 2.5), (0, y, -1.25))
        for i, pin in enumerate(names):
            x = (7 - i) * PITCH
            bm_box(bm_pins, (0.64, 0.64, 1.0), (x, y, T + 0.5))
            bm_cyl(bm_solder, 0.95, 0.6, (x, y, T + 0.3), radius_end=0.45, segments=12)
            text(f"Pin label {pin} {y > 0}", pin, 0.9, (x, y - 2.3 if y > 0 else y + 2.3, T + 0.01), M["silk"], g)
    obj_from_bm("Header strips", bm_strip, M["plastic_black"], g, bevel=0.2)
    obj_from_bm("Header pin tips", bm_pins, M["gold"], g)
    obj_from_bm("Solder joints", bm_solder, M["solder"], g)

    # USB end (-x): micro-USB, EN/BOOT buttons, USB-serial chip, regulator, LEDs
    box("Micro USB", (5.8, 7.6, 2.8), (-25.75 + 2.3, 0, T + 1.4), M["shield"], g, bevel=0.3)
    box("Micro USB opening", (0.4, 6.0, 1.4), (-25.75 - 0.62, 0, T + 1.4), M["plastic_black"], g)
    bm_base, bm_cap = bmesh.new(), bmesh.new()
    for y in (8.0, -8.0):
        bm_box(bm_base, (3.6, 5.0, 1.5), (-21.5, y, T + 0.75))
        bm_cyl(bm_cap, 1.1, 1.0, (-21.5, y, T + 2.0), segments=16)
    obj_from_bm("Button bases (EN, BOOT)", bm_base, M["button"], g, bevel=0.2)
    obj_from_bm("Button caps", bm_cap, M["plastic_black"], g)
    box("CH340 USB-serial chip", (4.9, 4.9, 1.0), (-13.5, 3.0, T + 0.5), M["chip"], g, bevel=0.15)
    text("CH340 print", "CH340", 0.75, (-13.5, 3.0, T + 1.01), M["silk"], g)
    box("AMS1117 regulator", (6.5, 3.5, 1.6), (-12.5, -5.5, T + 0.8), M["chip"], g, bevel=0.15)
    box("Regulator tab", (3.0, 1.4, 0.2), (-12.5, -8.0, T + 0.1), M["solder"], g)
    box("Power LED", (1.6, 0.8, 0.6), (-18.2, 4.0, T + 0.3), M["led_red"], g)
    box("Blue LED (D2)", (1.6, 0.8, 0.6), (-18.2, -4.0, T + 0.3), M["led_blue"], g)
    bm = bmesh.new()
    for x, y in ((-7.5, 6.5), (-7.5, -6.5), (-4.5, 6.5), (-4.5, -6.5), (-16.0, 0.0), (-9.0, 0.0), (-2.0, 0.0)):
        bm_box(bm, (1.0, 0.5, 0.45), (x, y, T + 0.23))
    obj_from_bm("SMD resistors/caps", bm, M["passive"], g)
    text("Board name", "ESP32 DEVKIT", 1.0, (-4.0, -3.2, T + 0.01), M["silk"], g)


def build_hcsr04(M, root, name, pos, angle):
    # Local frame: x along the board, +y = where the cans point, z up. Stands on its 4 jumper housings.
    g = group(f"HC-SR04 {name}", root, loc=(pos[0], pos[1], 26.8), rot=(0, 0, math.radians(angle)))
    box(f"{name} PCB", (45, 1.6, 20), (0, 0, 0), M["pcb_blue"], g, bevel=0.3)

    bm_cans, bm_mesh, bm_holes = bmesh.new(), bmesh.new(), bmesh.new()
    for cx in (-13, 13):
        bm_cyl(bm_cans, 8, 12, (cx, 6.8, 0), axis=(0, 1, 0), segments=40)
        bm_cyl(bm_mesh, 6.6, 0.4, (cx, 12.85, 0), axis=(0, 1, 0), segments=40)
    for x in (-20.5, 20.5):
        for z in (-7.5, 7.5):
            bm_cyl(bm_holes, 1.6, 0.1, (x, 0.82, z), axis=(0, 1, 0), segments=16)
    obj_from_bm(f"{name} transducers", bm_cans, M["can"], g, bevel=0.4)
    obj_from_bm(f"{name} transducer mesh", bm_mesh, M["mesh"], g)
    obj_from_bm(f"{name} mounting holes", bm_holes, M["solder"], g)
    box(f"{name} crystal", (10, 3.6, 4.2), (0, 2.6, 6.6), M["can"], g, bevel=0.6)

    bm = bmesh.new()
    for x in (-12, 0, 12):
        bm_box(bm, (5, 1.5, 4), (x, -1.55, -2))
    obj_from_bm(f"{name} chips (back)", bm, M["chip"], g)

    text(f"{name} print", "HC-SR04", 2.4, (0, 0.82, -6.4), M["silk"], g, rot=FRONT_TEXT)
    text(f"{name} T", "T", 1.4, (13, 0.82, -9.0), M["silk"], g, rot=FRONT_TEXT)
    text(f"{name} R", "R", 1.4, (-13, 0.82, -9.0), M["silk"], g, rot=FRONT_TEXT)

    # Header on the bottom edge; seen from the front, left to right: VCC Trig Echo Gnd
    pins = {"VCC": 3.81, "Trig": 1.27, "Echo": -1.27, "Gnd": -3.81}
    box(f"{name} header", (10.16, 2.5, 2.5), (0, 0, -11.25), M["plastic_black"], g, bevel=0.2)
    bm = bmesh.new()
    for pin, x in pins.items():
        bm_box(bm, (2.4, 2.4, 14), (x, 0, -19.5))
        text(f"{name} {pin} label", pin, 0.85, (x, 0.82, -9.2), M["silk"], g, rot=FRONT_TEXT)
    obj_from_bm(f"{name} jumper housings", bm, M["plastic_black"], g, bevel=0.25)

    bm = bmesh.new()
    bm_cyl(bm, 0.5, 200, (0, 12.8 + 100, 0), axis=(0, 1, 0), radius_end=200 * math.tan(math.radians(15)), segments=48)
    obj_from_bm(f"{name} sound beam", bm, M["beam"], g, coll="Sound beams")

    # Live parts, hidden until live_link.py runs: a 1 mm cone that gets scaled to the measured
    # distance (its end cap is the obstacle), and the distance floating above the sensor
    bm = bmesh.new()
    bm_cyl(bm, 0.001, 1.0, (0, 0.5, 0), axis=(0, 1, 0), radius_end=math.tan(math.radians(15)), segments=48)
    for f in bm.faces:
        f.material_index = 1 if f.normal.y > 0.9 else 0
    live = obj_from_bm(f"Live beam {name}", bm, [mat(f"Live beam {name}", "#5aa9ff", emission=1.0, alpha=0.22),
                                                 mat(f"Live obstacle {name}", "#5aa9ff", emission=2.0, alpha=0.9)],
                       g, coll="Live", loc=(0, 12.8, 0))
    live.scale = (300, 300, 300)
    live.hide_viewport = live.hide_render = True
    label = text(f"Live distance {name}", "--", 12, (pos[0], pos[1], 72), mat(f"Live text {name}", "#5aa9ff", emission=2.0),
                 root, rot=(math.radians(90), 0, 0), coll="Live")
    label.hide_viewport = label.hide_render = True

    # Where each jumper leaves the bottom of its housing, in model space
    R = Matrix.Rotation(math.radians(angle), 3, "Z")
    origin = Vector((pos[0], pos[1], 26.8))
    return {pin: origin + R @ Vector((x, 0, -26.5)) for pin, x in pins.items()}


def build_resistor(M, root, name, h1, h2, bands, standing):
    bm_body, bm_lead = bmesh.new(), bmesh.new()
    band_bms = {b: bmesh.new() for b in set(bands)}
    a, b = hole(*h1), hole(*h2)
    if standing:
        # Body upright over the first hole, the far lead bent over to the second hole
        base = BB_TOP + 1.5
        bm_cyl(bm_body, 1.2, 6.3, (a.x, a.y, base + 3.15), segments=20)
        for k, (off, band) in enumerate(zip((5.3, 4.3, 3.3, 1.0), bands)):
            bm_cyl(band_bms[band], 1.28, 0.55, (a.x, a.y, base + off), segments=20)
        wire(f"{name} lead 1", [(a.x, a.y, BB_TOP - 1.5), (a.x, a.y, base)], M["lead"], root, 0.3, smooth=False)
        wire(f"{name} lead 2", [(a.x, a.y, base + 6.3), (a.x, a.y, base + 7.6), (b.x, b.y, base + 7.6), (b.x, b.y, BB_TOP - 1.5)],
             M["lead"], root, 0.3, smooth=False)
    else:
        # Lying flat between the two holes
        z = BB_TOP + 2.0
        mid, axis = (a + b) / 2, (b - a).normalized()
        bm_cyl(bm_body, 1.2, 6.3, (mid.x, mid.y, z), axis=axis, segments=20)
        for off, band in zip((-2.2, -1.2, -0.2, 2.2), bands):
            c = mid + axis * off
            bm_cyl(band_bms[band], 1.28, 0.55, (c.x, c.y, z), axis=axis, segments=20)
        for p, end in ((a, mid - axis * 3.15), (b, mid + axis * 3.15)):
            wire(f"{name} lead", [(p.x, p.y, BB_TOP - 1.5), (p.x, p.y, z), (end.x, end.y, z)], M["lead"], root, 0.3, smooth=False)
    obj_from_bm(f"{name} body", bm_body, M["resistor"], root, bevel=0.3)
    for band, bm in band_bms.items():
        obj_from_bm(f"{name} {band} band", bm, M[band], root)


def build_buzzer(M, root):
    a, b = hole(*BUZZER_PLUS), hole(*BUZZER_MINUS)
    c = (a + b) / 2
    g = group("Buzzer TMB12A05", root, loc=(c.x, c.y, BB_TOP + 0.4))
    bm = bmesh.new()
    bm_cyl(bm, 6, 9.5, (0, 0, 4.75), segments=48)
    obj_from_bm("Buzzer body", bm, M["buzzer"], g, bevel=0.5)
    bm = bmesh.new()
    bm_cyl(bm, 1.0, 0.3, (0, 0, 9.55), segments=20)
    obj_from_bm("Buzzer sound hole", bm, M["plastic_black"], g)
    text("Buzzer + mark", "+", 2.2, (-3.6, 0, 9.52), M["silk"], g)

    # Sound rings for the live link, hidden until it runs
    ring_mat = mat("Live buzzer ring", "#ff2a2a", emission=1.0, alpha=0.6)
    for k in range(3):
        cu = bpy.data.curves.new(f"Live buzzer ring {k}", "CURVE")
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.45, 2
        sp = cu.splines.new("POLY")
        sp.points.add(47)
        for i, pt in enumerate(sp.points):
            a = 2 * math.pi * i / 48
            pt.co = (7.5 * math.cos(a), 7.5 * math.sin(a), 0, 1)
        sp.use_cyclic_u = True
        ring = add_obj(f"Live buzzer ring {k}", cu, ring_mat, g, "Live", loc=(0, 0, 10.5 + k))
        ring.hide_viewport = ring.hide_render = True


def male_end_top(h):
    return Vector((h.x, h.y, BB_TOP + 14))


def jumper_arc(M, root, name, h1, h2, color, housings):
    a, b = male_end_top(h1), male_end_top(h2)
    for h in (h1, h2):
        bm_box(housings, (2.4, 2.4, 14), (h.x, h.y, BB_TOP + 7))
    lift = 6 + 0.22 * (b - a).length
    mid = (a + b) / 2 + Vector((0, 0, lift))
    wire(name, [a, a + Vector((0, 0, 6)), mid, b + Vector((0, 0, 6)), b], M[color], root)


def jumper_flat(M, root, name, h1, h2, color):
    z = BB_TOP + 0.8
    wire(name, [(h1.x, h1.y, BB_TOP - 1.5), (h1.x, h1.y, z), (h2.x, h2.y, z), (h2.x, h2.y, BB_TOP - 1.5)],
         M[color], root, radius=0.5, smooth=False)


def sensor_wire(M, root, name, start, h, color, idx, housings):
    """Female end on the sensor pin, along the desk, up over the breadboard edge, male end in the hole."""
    bm_box(housings, (2.4, 2.4, 14), (h.x, h.y, BB_TOP + 7))
    top = male_end_top(h)
    s, t = start.xy, top.xy
    away = (s - t).normalized()
    edge = t.copy()
    while abs(edge.x) < BB_SIZE[0] / 2 + 6 and abs(edge.y) < BB_SIZE[1] / 2 + 6:
        edge += away
    side = Vector((-away.y, away.x)) * (idx - 1.5) * 1.4
    toward = -away
    mid = (s + edge) / 2 + side
    pts = [
        start,
        Vector((*(s + (edge - s).normalized() * 8), 0.7)),
        Vector((*mid, 0.7)),
        Vector((*edge, 0.9)),
        Vector((*(edge + toward * 4), BB_TOP + 22)),
        Vector((*t, top.z + 9)),
        top,
    ]

    def flat(a, b):
        d = pts[b] - pts[a]
        return Vector((d.x, d.y, 0))

    # Lie flat along the desk (points 1-3), then turn straight up beside the breadboard
    handles = {1: (flat(0, 2), flat(0, 2)), 2: (flat(1, 3), flat(1, 3)), 3: (flat(2, 3), (0, 0, 1))}
    wire(name, pts, M[color], root, handles=handles)


def build_wiring(M, root, sensor_pins):
    housings = bmesh.new()
    for (name, _pos, _angle, holes), pins in zip(SENSORS, sensor_pins):
        for idx, pin in enumerate(("VCC", "Trig", "Echo", "Gnd")):
            row, col = holes[pin]
            h = hole(col, row)
            sensor_wire(M, root, f"{name} {pin} wire", pins[pin], h, WIRE_COLOR[pin], idx, housings)

    for i, (div, (name, *_)) in enumerate(zip(DIVIDERS, SENSORS)):
        (c1, r1), (c2, r2) = div["r1k"]
        build_resistor(M, root, f"{name} 1k", (c1, r1), (c2, r2), ("band_brown", "band_black", "band_red", "band_gold"), False)
        (c1, r1), (c2, r2) = div["r2k"]
        build_resistor(M, root, f"{name} 2k", (c1, r1), (c2, r2), ("band_red", "band_black", "band_red", "band_gold"), True)
        (col, row), pin = div["jumper"]
        jumper_arc(M, root, f"{name} Echo to {pin}", hole(col, row), hole(esp_col(pin), "a"), "wire_blue", housings)

    jumper_flat(M, root, "VIN to + rail", hole(esp_col("VIN"), "a"), hole(esp_col("VIN"), "top+"), "wire_red")
    jumper_flat(M, root, "GND to - rail", hole(esp_col("GND"), "a"), hole(esp_col("GND"), "top-"), "wire_black")
    jumper_arc(M, root, "D13 to buzzer +", hole(esp_col("D13"), "a"), hole(BUZZER_PLUS[0], "j"), "wire_pink", housings)
    jumper_flat(M, root, "Buzzer - to - rail", hole(BUZZER_MINUS[0], "j"), hole(BUZZER_MINUS[0], "bot-"), "wire_black")
    jumper_arc(M, root, "Top - rail to bottom - rail", hole(27, "top-"), hole(27, "bot-"), "wire_black", housings)
    obj_from_bm("Jumper housings (on breadboard)", housings, M["plastic_black"], root, coll="Wires", bevel=0.25)


def build_labels(M, root):
    for body, x, y in (("LEFT", -125, -22), ("CENTER", 52, 108), ("RIGHT", 125, -22),
                       ("ESP32", -16.5, -36), ("BUZZER", 33, -36)):
        text(f"Label {body}", body, 6, (x, y, 0.05), M["label"], root, coll="Labels")
    status = text("Live status", "", 6, (0, -55, 8), M["label"], root, rot=(math.radians(90), 0, 0), coll="Live")
    status.hide_viewport = status.hide_render = True


def embed_live_link():
    """Store live_link.py in the file and show it in the Scripting workspace's text editor."""
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_link.py")) as f:
        script = bpy.data.texts.new("live_link.py")
        script.from_string(f.read())
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = script


def build_optional_desk(root):
    """A wooden desk under the parts, hidden by default (eye icon on 'Desk (optional)')."""
    bm = bmesh.new()
    bm_box(bm, (700, 520, 20), (0, 40, -10))
    obj_from_bm("Desk", bm, wood_material(), root, coll="Desk (optional)", bevel=2.0)


# ---------------------------------------------------------------- scene setup
HDRI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hdri", "artist_workshop_4k.hdr")
HIDDEN_BY_DEFAULT = ("Labels", "Sound beams", "Desk (optional)")


def try_set(obj, attr, value):
    """Set a setting that only exists in some Blender versions."""
    try:
        setattr(obj, attr, value)
    except (AttributeError, TypeError):
        pass


def setup_world(scene):
    """Real photographed environment as background and light (bundled studio light if the HDRI is missing)."""
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    bg = nodes.get("Background")
    path = HDRI if os.path.exists(HDRI) else bpy.utils.system_resource("DATAFILES", path="studiolights/world/interior.exr")
    env = nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path)
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0, 0, math.radians(200))
    links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0


def setup_renderer(scene):
    """EEVEE with ray-traced reflections and soft shadows, filmic (AgX) colour."""
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    eevee = scene.eevee
    try_set(eevee, "use_raytracing", True)
    try_set(eevee, "taa_samples", 64)
    try_set(eevee, "taa_render_samples", 128)
    try_set(eevee, "use_shadows", True)
    try_set(eevee, "shadow_ray_count", 2)
    scene.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue


def find_layer_collection(layer, name):
    if layer.name == name:
        return layer
    for child in layer.children:
        found = find_layer_collection(child, name)
        if found:
            return found
    return None


def setup_scene(target, eye):
    scene = bpy.context.scene
    scene.unit_settings.length_unit = "MILLIMETERS"
    setup_world(scene)
    setup_renderer(scene)
    for name in HIDDEN_BY_DEFAULT:
        COLLECTIONS[name].hide_render = True
        find_layer_collection(bpy.context.view_layer.layer_collection, name).hide_viewport = True

    # Soft key light from above plus a gentle sun, on top of the environment light
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy, sun.data.angle = 1.2, math.radians(4)
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(35))
    area = bpy.data.objects.new("Softbox", bpy.data.lights.new("Softbox", "AREA"))
    area.data.energy, area.data.size = 12, 0.5
    area.location = (0.1, -0.15, 0.5)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens, cam.data.clip_start = 40, 0.005
    for o in (sun, area, cam):
        collection("Lights & camera").objects.link(o)

    target, eye = Vector(target), Vector(eye)
    rot = (target - eye).to_track_quat("-Z", "Y")
    cam.location, cam.rotation_euler = eye, rot.to_euler()
    scene.camera = cam

    # Open straight into the realistic (Rendered) view, without Blender's helper lines and outlines
    for screen in bpy.data.screens:
        for area_ in screen.areas:
            if area_.type != "VIEW_3D":
                continue
            for space in area_.spaces:
                if space.type == "VIEW_3D":
                    space.shading.type = "RENDERED"
                    space.clip_start, space.clip_end = 0.001, 100
                    space.overlay.show_overlays = False
                    r3d = space.region_3d
                    r3d.view_perspective = "PERSP"
                    r3d.view_location, r3d.view_rotation = target, rot
                    r3d.view_distance = (target - eye).length


def render_preview(path):
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else "belt_for_blind.blend"
    preview = argv[1] if len(argv) > 1 else None

    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    M = make_materials()
    root = group("Belt for Blind (mm)", None, coll="Electronics")
    root.scale = (0.001, 0.001, 0.001)

    build_breadboard(M, root)
    build_esp32(M, root)
    sensor_pins = [build_hcsr04(M, root, name, pos, angle) for name, pos, angle, _ in SENSORS]
    build_buzzer(M, root)
    build_wiring(M, root, sensor_pins)
    build_labels(M, root)
    build_optional_desk(root)
    embed_live_link()

    setup_scene(target=(0, 0.03, 0.01), eye=(0.12, -0.33, 0.30))
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f"Saved {out} ({len(bpy.data.objects)} objects)")
    if preview:
        render_preview(preview)
        print(f"Preview {preview}")


main()
