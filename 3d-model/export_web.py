"""Export the saved Blender prototype for the separate live 3D web page.

Run from the project root:
  /Applications/Blender.app/Contents/MacOS/Blender -b 3d-model/belt_for_blind.blend -P 3d-model/export_web.py

Only the in-memory scene is changed; the .blend source is never overwritten.
"""
import json
import math
from pathlib import Path

import bpy

PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "tools/live-view/assets"
OUT.mkdir(parents=True, exist_ok=True)


def main():
    root = bpy.data.objects["Belt for Blind (mm)"]
    root.rotation_mode = "QUATERNION"
    root.rotation_quaternion = (1, 0, 0, 0)
    # A .blend can be saved while the live link is running. Restore the motor
    # metal instead of exporting a transient red alert as its resting colour.
    for name in ("Left", "Center", "Right"):
        material = bpy.data.materials[f"Motor top {name}"]
        bsdf = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        rgb = tuple((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) for v in (201 / 255, 206 / 255, 212 / 255))
        bsdf.inputs["Base Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = 0
        material.diffuse_color = (*rgb, 1)

    # Export curves and printed text as real geometry, with the original names
    # retained in extras (GLTFLoader sanitizes object names).
    for coll in bpy.data.collections:
        coll.hide_viewport = coll.hide_render = False

    def show_layer(layer):
        layer.hide_viewport = layer.exclude = False
        for child in layer.children:
            show_layer(child)

    show_layer(bpy.context.view_layer.layer_collection)
    keep = []
    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_viewport = obj.hide_render = False
        collections = {c.name for c in obj.users_collection}
        if collections & {"Breadboard", "Electronics", "Wires"} or obj.name.startswith(("Live beam ", "Live motor ring ")):
            obj["belt_name"] = obj.name
            keep.append(obj)

    bpy.ops.object.select_all(action="DESELECT")
    curves = [o for o in keep if o.type in {"CURVE", "FONT"}]
    for obj in curves:
        obj.select_set(True)
    if curves:
        bpy.context.view_layer.objects.active = curves[0]
        bpy.ops.object.convert(target="MESH")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.data.objects:
        if "belt_name" in obj:
            obj.select_set(True)

    # Keep Blender's Z-up coordinates so the live_link.py quaternion math and
    # the camera position can be used unchanged in the browser.
    bpy.ops.export_scene.gltf(
        filepath=str(OUT / "belt_for_blind.glb"), export_format="GLB",
        use_selection=True, export_yup=False, export_apply=True,
        export_extras=True, export_animations=False, export_cameras=False,
        export_lights=False,
    )

    # Preserve the source's view, and the mounting correction used by its link.
    camera = bpy.context.scene.camera
    metadata = {
        "camera": list(camera.location), "target": [0, -0.012, 0.01],
        "fov": math.degrees(camera.data.angle), "turnSensorDeg": 0,
        "environmentRotationDeg": 200,
    }
    import ast
    source = (PROJECT / "3d-model/live_link.py").read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TURN_SENSOR_DEG" for t in node.targets):
            metadata["turnSensorDeg"] = ast.literal_eval(node.value)
    (OUT / "scene.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Exported live web model to {OUT}")


main()
