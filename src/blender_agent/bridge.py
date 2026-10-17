"""In-Blender side of blender-agent. Started by the client as

    blender [-b] --factory-startup --python-exit-code 1 --python bridge.py -- --socket PATH [--allow-exec]

It connects to the client's Unix socket and serves framed JSON-RPC requests.
Every bpy access happens on Blender's main thread:

* background (``-b``): this script blocks the main thread in a serve loop;
* GUI: a reader thread only moves frames into a queue and one persistent
  ``bpy.app.timers`` callback, registered here on the main thread, executes them.
"""

import base64
import io
import math
import os
import queue
import re
import socket
import sys
import tempfile
import threading
import traceback
from contextlib import redirect_stdout

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import protocol as wire  # noqa: E402  (sibling module, loaded without the package)


class BridgeError(Exception):
    """An error the agent caused and can fix (bad name, unsupported mode, ...)."""


def _parse_args(argv):
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    socket_path, allow_exec = None, False
    i = 0
    while i < len(args):
        if args[i] == "--socket":
            socket_path = args[i + 1]
            i += 2
        elif args[i] == "--allow-exec":
            allow_exec = True
            i += 1
        else:
            raise SystemExit(f"blender-agent bridge: unknown argument {args[i]!r}")
    if not socket_path:
        raise SystemExit("blender-agent bridge: --socket PATH is required")
    return socket_path, allow_exec


SOCKET_PATH, ALLOW_EXEC = _parse_args(sys.argv)
BACKGROUND = bpy.app.background
CHECKPOINT_DIR = tempfile.mkdtemp(prefix="blender-agent-ckpt-")
_checkpoints = {}


# --------------------------------------------------------------------- helpers

def _vec(v):
    return [round(float(x), 6) for x in v]


def _resolve_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        raise BridgeError(f"no object named {name!r}")
    return obj


def _json_value(value):
    """Convert an RNA value into JSON-compatible data."""
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, bpy.types.ID):
        return {"id_type": type(value).__name__, "name": value.name}
    if isinstance(value, bpy.types.bpy_struct):
        return {"struct": type(value).__name__, "path": repr(value)}
    if isinstance(value, set):
        return sorted(value)
    try:
        return [_json_value(v) for v in value]
    except TypeError:
        return repr(value)


def _area_override(area_type):
    window = bpy.context.window or (bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None)
    if window is None:
        return {}
    for area in window.screen.areas:
        if area.type == area_type:
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            override = {"window": window, "screen": window.screen, "area": area}
            if region is not None:
                override["region"] = region
            return override
    raise BridgeError(f"no {area_type} area in the current screen")


def _world_bbox(objects):
    corners = [obj.matrix_world @ Vector(c) for obj in objects for c in obj.bound_box]
    if not corners:
        return Vector((0, 0, 0)), 1.0
    lo = Vector(min(c[i] for c in corners) for i in range(3))
    hi = Vector(max(c[i] for c in corners) for i in range(3))
    return (lo + hi) / 2, max((hi - lo).length / 2, 0.5)


# ------------------------------------------------------------------- handlers

def ping():
    return {
        "pong": True,
        "blender_version": bpy.app.version_string,
        "background": BACKGROUND,
        "allow_exec": ALLOW_EXEC,
    }


def _object_summary(obj):
    return {
        "name": obj.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "location": _vec(obj.location),
        "rotation_euler": _vec(obj.rotation_euler),
        "scale": _vec(obj.scale),
        "dimensions": _vec(obj.dimensions),
        "visible": obj.visible_get(),
        "selected": obj.select_get(),
        "collections": [c.name for c in obj.users_collection],
        "data": obj.data.name if obj.data else None,
    }


def scene_graph():
    scene = bpy.context.scene
    active = bpy.context.view_layer.objects.active
    return {
        "scene": scene.name,
        "file": bpy.data.filepath or None,
        "frame_current": scene.frame_current,
        "frame_range": [scene.frame_start, scene.frame_end],
        "render_engine": scene.render.engine,
        "camera": scene.camera.name if scene.camera else None,
        "active_object": active.name if active else None,
        "mode": bpy.context.mode,
        "objects": [_object_summary(o) for o in scene.objects],
    }


def object_info(name):
    obj = _resolve_object(name)
    info = _object_summary(obj)
    center, radius = _world_bbox([obj])
    info["world_bbox_center"] = _vec(center)
    info["world_bbox_radius"] = round(radius, 6)
    info["modifiers"] = [{"name": m.name, "type": m.type, "show_viewport": m.show_viewport} for m in obj.modifiers]
    info["materials"] = [slot.material.name if slot.material else None for slot in obj.material_slots]
    info["custom_properties"] = {k: _json_value(obj[k]) for k in obj.keys() if not k.startswith("_")}
    if obj.type == "MESH":
        mesh = obj.data
        info["mesh"] = {"vertices": len(mesh.vertices), "edges": len(mesh.edges), "polygons": len(mesh.polygons)}
    elif obj.type == "LIGHT":
        info["light"] = {"type": obj.data.type, "energy": obj.data.energy, "color": _vec(obj.data.color)}
    elif obj.type == "CAMERA":
        info["camera"] = {"lens": obj.data.lens, "type": obj.data.type}
    return info


def call_operator(idname, params=None, area_type=None, execution_context="EXEC_DEFAULT"):
    module_name, _, op_name = idname.partition(".")
    module = getattr(bpy.ops, module_name, None)
    if module is None or not op_name or op_name not in dir(module):
        raise BridgeError(f"unknown operator {idname!r}; use search_operators to find one")
    op = getattr(module, op_name)
    override = _area_override(area_type or "VIEW_3D")
    with bpy.context.temp_override(**override):
        if not op.poll():
            raise BridgeError(f"{idname}.poll() failed in the current context (mode={bpy.context.mode!r})")
        # The positional ``undo`` flag makes Python-invoked operators push an undo
        # step, which only exists in GUI sessions (``-b`` has no undo stack).
        result = op(execution_context, not BACKGROUND, **(params or {}))
    return {"result": sorted(result)}


def _resolve_datablock(collection, name):
    coll = getattr(bpy.data, collection, None)
    if not isinstance(coll, bpy.types.bpy_prop_collection):
        raise BridgeError(f"bpy.data has no collection {collection!r}")
    block = coll.get(name)
    if block is None:
        raise BridgeError(f"bpy.data.{collection} has no {name!r}")
    return block


_SINGLE_QUOTED_KEY = re.compile(r"\['((?:[^'\\]|\\.)*)'\]")


def _normalize_path(path):
    # RNA path_resolve only understands double-quoted keys: modifiers["Bevel"].
    return _SINGLE_QUOTED_KEY.sub(lambda m: '["' + m.group(1).replace('"', '\\"') + '"]', path)


def _split_path(path):
    # 'modifiers["Bevel"].width' -> owner path 'modifiers["Bevel"]', attribute 'width'
    path = _normalize_path(path)
    if "." in path and not path.endswith("]"):
        owner, attr = path.rsplit(".", 1)
        return owner, attr
    return "", path


def get_property(collection, name, path):
    block = _resolve_datablock(collection, name)
    try:
        return {"value": _json_value(block.path_resolve(_normalize_path(path)))}
    except ValueError as exc:
        raise BridgeError(f"cannot resolve {path!r} on {collection}[{name!r}]: {exc}") from exc


def set_property(collection, name, path, value):
    block = _resolve_datablock(collection, name)
    owner_path, attr = _split_path(path)
    try:
        owner = block.path_resolve(owner_path) if owner_path else block
    except ValueError as exc:
        raise BridgeError(f"cannot resolve {owner_path!r} on {collection}[{name!r}]: {exc}") from exc
    if not hasattr(owner, attr):
        raise BridgeError(f"{type(owner).__name__} has no property {attr!r}")
    setattr(owner, attr, value)
    return {"value": _json_value(getattr(owner, attr))}


def exec_python(code):
    if not ALLOW_EXEC:
        raise BridgeError("exec_python is disabled; start the session with allow_exec=True")
    namespace = {"bpy": bpy, "__name__": "__blender_agent__"}
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exec(compile(code, "<agent>", "exec"), namespace)
    return {"stdout": buffer.getvalue(), "result": _json_value(namespace.get("result"))}


def _temporary_camera(scene):
    visible = [o for o in scene.objects if o.visible_get() and o.type not in {"CAMERA", "LIGHT"}]
    center, radius = _world_bbox(visible)
    data = bpy.data.cameras.new("blender_agent_tmp_cam")
    cam = bpy.data.objects.new("blender_agent_tmp_cam", data)
    scene.collection.objects.link(cam)
    direction = Vector((1.0, -1.0, 0.8)).normalized()
    distance = radius / math.tan(data.angle / 2) * 1.1
    cam.location = center + direction * distance
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    data.clip_end = max(data.clip_end, distance + radius * 4)
    return cam


def _render_engine():
    requested = os.environ.get("BLENDER_AGENT_RENDER_ENGINE")
    return requested or "BLENDER_WORKBENCH"


def _render_png(width, height):
    scene = bpy.context.scene
    render = scene.render
    saved = {
        "engine": render.engine,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
        "filepath": render.filepath,
        "file_format": render.image_settings.file_format,
        "camera": scene.camera,
    }
    temp_cam = None
    path = os.path.join(CHECKPOINT_DIR, "render.png")
    try:
        if scene.camera is None:
            temp_cam = _temporary_camera(scene)
            scene.camera = temp_cam
        render.engine = _render_engine()
        if render.engine == "CYCLES":
            scene.cycles.device = "CPU"
            scene.cycles.samples = 16
        render.resolution_x, render.resolution_y = width, height
        render.resolution_percentage = 100
        render.image_settings.file_format = "PNG"
        render.filepath = path
        bpy.ops.render.render(write_still=True)
        engine = render.engine
    finally:
        render.engine = saved["engine"]
        render.resolution_x = saved["resolution_x"]
        render.resolution_y = saved["resolution_y"]
        render.resolution_percentage = saved["resolution_percentage"]
        render.filepath = saved["filepath"]
        render.image_settings.file_format = saved["file_format"]
        scene.camera = saved["camera"]
        if temp_cam is not None:
            data = temp_cam.data
            bpy.data.objects.remove(temp_cam)
            bpy.data.cameras.remove(data)
    with open(path, "rb") as f:
        png = f.read()
    return png, {"method": "render", "engine": engine, "temporary_camera": temp_cam is not None}


def _viewport_png(width, height):
    import gpu  # only importable with a GPU context, i.e. not under -b
    import numpy as np

    override = _area_override("VIEW_3D")
    area, region = override["area"], override["region"]
    space = area.spaces.active
    scale = min(width / region.width, height / region.height, 1.0)
    w, h = max(1, int(region.width * scale)), max(1, int(region.height * scale))
    offscreen = gpu.types.GPUOffScreen(w, h)
    try:
        offscreen.draw_view3d(bpy.context.scene, bpy.context.view_layer, space, region,
                              space.region_3d.view_matrix, space.region_3d.window_matrix,
                              do_color_management=True)
        buf = offscreen.texture_color.read()
    finally:
        offscreen.free()
    buf.dimensions = w * h * 4
    pixels = np.asarray(buf, dtype=np.float32) / 255.0
    image = bpy.data.images.new("blender_agent_viewport", w, h, alpha=True)
    path = os.path.join(CHECKPOINT_DIR, "viewport.png")
    try:
        image.pixels.foreach_set(pixels.ravel())
        image.filepath_raw = path
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)
    with open(path, "rb") as f:
        png = f.read()
    return png, {"method": "viewport_offscreen", "width": w, "height": h}


def screenshot(width=640, height=480, source="auto"):
    if source not in {"auto", "render", "viewport"}:
        raise BridgeError("source must be 'auto', 'render' or 'viewport'")
    if source == "viewport" and BACKGROUND:
        raise BridgeError("viewport capture needs a GUI session; background sessions can only render")
    if source == "viewport" or (source == "auto" and not BACKGROUND):
        png, meta = _viewport_png(width, height)
    else:
        png, meta = _render_png(width, height)
        meta.update(width=width, height=height)
    meta["png_base64"] = base64.b64encode(png).decode("ascii")
    return meta


def checkpoint(label=None):
    key = f"ckpt{len(_checkpoints) + 1}"
    path = os.path.join(CHECKPOINT_DIR, f"{key}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, check_existing=False)
    _checkpoints[key] = {"path": path, "label": label, "file": bpy.data.filepath or None}
    return {"checkpoint": key, "label": label}


def restore(checkpoint_id):
    entry = _checkpoints.get(checkpoint_id)
    if entry is None:
        raise BridgeError(f"unknown checkpoint {checkpoint_id!r}; known: {sorted(_checkpoints)}")
    bpy.ops.wm.open_mainfile(filepath=entry["path"], load_ui=False)
    return {"restored": checkpoint_id, "objects": len(bpy.context.scene.objects)}


def undo(steps=1):
    if BACKGROUND:
        raise BridgeError("background sessions have no undo stack; use checkpoint/restore")
    for _ in range(steps):
        with bpy.context.temp_override(**_area_override("VIEW_3D")):
            bpy.ops.ed.undo()
    return {"undone": steps}


def save(filepath):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(filepath), check_existing=False)
    return {"file": bpy.data.filepath}


def open_file(filepath):
    if not os.path.isfile(filepath):
        raise BridgeError(f"no such file: {filepath}")
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(filepath), load_ui=False)
    return {"file": bpy.data.filepath, "objects": len(bpy.context.scene.objects)}


def _iter_operators():
    for module_name in dir(bpy.ops):
        module = getattr(bpy.ops, module_name)
        for op_name in dir(module):
            try:
                yield f"{module_name}.{op_name}", getattr(module, op_name).get_rna_type()
            except (AttributeError, KeyError, RuntimeError):
                continue


def search_operators(query, limit=20):
    terms = query.lower().split()
    hits = []
    for idname, rna in _iter_operators():
        haystack = f"{idname} {rna.name} {rna.description}".lower()
        if all(t in haystack for t in terms):
            score = sum(t in idname for t in terms) * 2 + sum(t in rna.name.lower() for t in terms)
            hits.append((-score, idname, rna))
    hits.sort(key=lambda h: (h[0], h[1]))
    return {
        "total": len(hits),
        "operators": [{"idname": i, "name": r.name, "description": r.description} for _, i, r in hits[:limit]],
    }


def describe_operator(idname):
    module_name, _, op_name = idname.partition(".")
    module = getattr(bpy.ops, module_name, None)
    if module is None or op_name not in dir(module):
        raise BridgeError(f"unknown operator {idname!r}")
    rna = getattr(module, op_name).get_rna_type()
    props = []
    for p in rna.properties:
        if p.identifier == "rna_type":
            continue
        entry = {"name": p.identifier, "type": p.type, "description": p.description}
        if p.type == "ENUM":
            entry["enum_items"] = [i.identifier for i in p.enum_items]
        elif getattr(p, "array_length", 0):
            entry["array_length"] = p.array_length
        props.append(entry)
    return {"idname": idname, "name": rna.name, "description": rna.description, "properties": props}


HANDLERS = {
    "ping": ping,
    "scene_graph": scene_graph,
    "object_info": object_info,
    "call_operator": call_operator,
    "get_property": get_property,
    "set_property": set_property,
    "exec_python": exec_python,
    "screenshot": screenshot,
    "checkpoint": checkpoint,
    "restore": restore,
    "undo": undo,
    "save": save,
    "open_file": open_file,
    "search_operators": search_operators,
    "describe_operator": describe_operator,
}


# --------------------------------------------------------------------- serving

def handle(request):
    request_id = request.get("id")
    method = request.get("method")
    handler = HANDLERS.get(method)
    if handler is None:
        return {"id": request_id, "ok": False,
                "error": {"type": "UnknownMethod", "message": f"unknown method {method!r}", "traceback": ""}}
    try:
        return {"id": request_id, "ok": True, "result": handler(**(request.get("params") or {}))}
    except Exception as exc:  # every failure goes back to the agent, the bridge keeps serving
        return {"id": request_id, "ok": False, "error": {
            "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}}


def _connect():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    wire.send_frame(sock, {"hello": "blender-agent", "pid": os.getpid(), **ping()})
    return sock


def serve_background():
    sock = _connect()
    try:
        while True:
            try:
                request = wire.recv_frame(sock)
            except wire.ConnectionClosed:
                return
            if request.get("method") == "quit":
                wire.send_frame(sock, {"id": request.get("id"), "ok": True, "result": {"quit": True}})
                return
            wire.send_frame(sock, handle(request))
    finally:
        sock.close()


def serve_gui():
    sock = _connect()
    inbox = queue.Queue()

    def reader():
        while True:
            try:
                inbox.put(wire.recv_frame(sock))
            except (wire.ProtocolError, OSError):
                inbox.put(None)
                return

    threading.Thread(target=reader, name="blender-agent-reader", daemon=True).start()

    def drain():
        while True:
            try:
                request = inbox.get_nowait()
            except queue.Empty:
                return 0.02
            if request is None or request.get("method") == "quit":
                if request is not None:
                    wire.send_frame(sock, {"id": request.get("id"), "ok": True, "result": {"quit": True}})
                sock.close()
                bpy.ops.wm.quit_blender()
                return None
            wire.send_frame(sock, handle(request))

    bpy.app.timers.register(drain, first_interval=0.0, persistent=True)


if BACKGROUND:
    serve_background()
else:
    serve_gui()
