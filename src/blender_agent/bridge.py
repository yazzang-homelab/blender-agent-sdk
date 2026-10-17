"""In-Blender side of blender-agent. Started by the client as

    blender [-b] [--disable-autoexec] [FILE.blend] [--factory-startup] [EXTRA_ARGS...] \
        --python-exit-code 1 --python bridge.py -- --socket PATH --workdir DIR [--allow-exec]

``DIR`` is owned by the client, which removes it after Blender exits; checkpoints
and screenshots are written there.

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
    socket_path, workdir, allow_exec = None, None, False
    i = 0
    while i < len(args):
        if args[i] == "--socket":
            socket_path = args[i + 1]
            i += 2
        elif args[i] == "--workdir":
            workdir = args[i + 1]
            i += 2
        elif args[i] == "--allow-exec":
            allow_exec = True
            i += 1
        else:
            raise SystemExit(f"blender-agent bridge: unknown argument {args[i]!r}")
    if not socket_path or not workdir:
        raise SystemExit("blender-agent bridge: --socket PATH and --workdir DIR are required")
    if not os.path.isdir(workdir):
        raise SystemExit(f"blender-agent bridge: --workdir {workdir!r} is not a directory")
    return socket_path, workdir, allow_exec


SOCKET_PATH, WORKDIR, ALLOW_EXEC = _parse_args(sys.argv)
BACKGROUND = bpy.app.background
_checkpoints = {}  # checkpoint id -> .blend path inside WORKDIR

# ------------------------------------------------------------- exec policy
#
# Without --allow-exec the agent must not be able to run Python through the back
# door of an operator. These operators run, install or eval() code (sources:
# 5.2/scripts/startup/bl_operators/{wm,presets,userpref,node,anim,file,assets}.py,
# bl_ui/generic_ui_list.py, editors/space_text/text_ops.cc, editors/space_script/).
# This closes code execution inside Blender; it is not a filesystem sandbox.

_EXEC_MODULES = {"script", "console", "preferences", "extensions"}
_EXEC_OPERATORS = {
    "text.run_script",        # runs a text block
    "anim.keying_set_export", # writes a Python script
    "wm.path_open",           # launches an external program
    "wm.url_open",
    "image.external_edit",
    "asset.open_containing_blend_file",  # starts another Blender with the user's auto-exec preference
    # eval()s every F-Curve and driver data_path (_animsys_refactor), and the agent can set those strings.
    "anim.update_animated_transform_constraints",
}
# String parameters that Python operators pass to eval()/exec().
_EVAL_PARAMS = {"data_path", "data_path_iter", "data_path_item", "eval_string", "list_path",
                "active_index_path", "prop_string"}


def _python_operator_module(op):
    cls = getattr(bpy.types, op.idname(), None)
    module = getattr(cls, "__module__", "bpy.types")
    return None if module == "bpy.types" else module


def _exec_refusal(idname, op, rna, params):
    """Reason this call would execute agent-controlled code, or None."""
    module_name = idname.partition(".")[0]
    if module_name in _EXEC_MODULES or idname in _EXEC_OPERATORS:
        return f"{idname} runs or installs code"
    py_module = _python_operator_module(op)
    if py_module is not None:
        names = {p.identifier for p in rna.properties}
        if names & _EVAL_PARAMS:
            return f"{idname} evaluates its {sorted(names & _EVAL_PARAMS)} parameters as Python"
        if py_module.endswith("presets"):
            return f"{idname} reads or writes Python preset scripts"
        # NodeAddOperator and every subclass (add_node, swap_node, the zone/group/bundle
        # adders) eval() each NodeSetting.value (bl_operators/node.py).
        settings = rna.properties.get("settings")
        if (params.get("settings") and settings is not None and settings.type == "COLLECTION"
                and settings.fixed_type.identifier == "NodeSetting"):
            return f"{idname} evaluates settings values as Python"
    if params.get("use_scripts"):
        return f"{idname} with use_scripts=True would run scripts embedded in the file"
    if params.get("use_trusted"):  # wm.previews_batch_*: a child Blender with --enable-autoexec
        return f"{idname} with use_trusted=True would run scripts embedded in the files"
    if params.get("load_ui"):
        return f"{idname} with load_ui=True would load the file's UI, whose redraws can render (Freestyle runs Python)"
    if params.get("app_template"):  # wm.read_homefile: an app template is a Python package it imports
        return f"{idname} with app_template would import the template's Python package"
    if idname == "wm.previews_batch_generate" and params.get("use_scenes"):
        return (f"{idname} with use_scenes=True renders each scene with its own settings in a child Blender, "
                "where Freestyle runs Python")
    return None


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
    if isinstance(value, bpy.types.bpy_prop_collection):  # names may repeat or be empty
        return [_json_value(v) for v in value]
    if hasattr(value, "keys") and hasattr(value, "values"):  # dict, IDPropertyGroup
        return {str(k): _json_value(v) for k, v in value.items()}
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


def _resolve_operator(idname):
    module_name, _, op_name = idname.partition(".")
    if module_name not in dir(bpy.ops) or op_name not in dir(getattr(bpy.ops, module_name)):
        raise BridgeError(f"unknown operator {idname!r}; use search_operators to find one")
    op = getattr(getattr(bpy.ops, module_name), op_name)
    return op, op.get_rna_type()


# Freestyle runs Python whenever it renders, whatever --disable-autoexec and use_scripts say:
# style-module text blocks in SCRIPT mode (BPY_run_text), and in EDITOR mode an expression built from
# view-layer and line-set names that escapes only quotes (FRS_freestyle.cpp:165-188). GUI sessions
# also render outside requests (a sequencer preview set to Rendered redraws scene strips through
# RE_RenderFrame). So without allow_exec the bridge keeps render.use_freestyle off in every scene,
# linked ones included: at startup and after every request, before control returns to the event loop.
# Nothing else can switch it on: the property is not animatable and accepts no drivers.

def _disable_freestyle():
    """Turn Freestyle off everywhere; returns the names of the scenes that had it on."""
    turned_off = []
    for scene in bpy.data.scenes:
        if scene.render.use_freestyle:
            scene.render.use_freestyle = False  # also allowed on linked scenes: a runtime-only change
            turned_off.append(scene.name)
    return sorted(turned_off)


if not ALLOW_EXEC and (_launch_scenes := _disable_freestyle()):
    # The launch file: nobody asked yet, so log it instead of failing a request.
    print(f"blender-agent: Freestyle turned off in scenes {_launch_scenes}", file=sys.stderr)


def call_operator(idname, params=None, area_type=None, execution_context="EXEC_DEFAULT"):
    op, rna = _resolve_operator(idname)
    params = dict(params or {})
    if not ALLOW_EXEC:
        reason = _exec_refusal(idname, op, rna, params)
        if reason is None and idname.startswith("render.") and execution_context.startswith("INVOKE"):
            # An invoked render runs as a job that outlives the request, while the Freestyle reset
            # only holds between requests.
            reason = f"{idname} with {execution_context} would start a render job that outlives the request"
        if reason:
            raise BridgeError(f"refused without allow_exec: {reason}")
        # use_scripts: do not fall back to the auto-exec preference. use_trusted: GUI sessions
        # re-use an operator's last properties, so pin the default explicitly. load_ui: a file's own
        # UI could redraw a sequencer preview that renders. use_scenes (previews only, default True):
        # the child Blender renders the file's scenes as they are, Freestyle included; object and
        # collection previews render in fresh scenes.
        flags = ["use_scripts", "use_trusted", "load_ui"]
        if idname == "wm.previews_batch_generate":
            flags.append("use_scenes")
        for flag in flags:
            if rna.properties.get(flag) is not None:
                params[flag] = False
    override = _area_override(area_type or "VIEW_3D")
    with bpy.context.temp_override(**override):
        if not op.poll():
            raise BridgeError(f"{idname}.poll() failed in the current context (mode={bpy.context.mode!r})")
        # The positional ``undo`` flag makes Python-invoked operators push an undo
        # step, which only exists in GUI sessions (``-b`` has no undo stack).
        result = op(execution_context, not BACKGROUND, **params)
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
    if not ALLOW_EXEC and value and path.rpartition(".")[2] == "use_freestyle":
        # The post-request reset would undo it, but a running GUI render job could read it first.
        raise BridgeError("refused without allow_exec: Freestyle runs Python when rendering")
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
        "cycles_device": scene.cycles.device,
        "cycles_samples": scene.cycles.samples,
    }
    temp_cam = None
    path = os.path.join(WORKDIR, "render.png")
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
        scene.cycles.device = saved["cycles_device"]
        scene.cycles.samples = saved["cycles_samples"]
        if temp_cam is not None:
            data = temp_cam.data
            bpy.data.objects.remove(temp_cam)
            bpy.data.cameras.remove(data)
    with open(path, "rb") as f:
        png = f.read()
    return png, {"method": "render", "engine": engine, "temporary_camera": temp_cam is not None}


def _viewport_png(width, height):
    import gpu  # GUI sessions only: drawing needs the window's GPU context
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
    path = os.path.join(WORKDIR, "viewport.png")
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
        raise BridgeError("viewport capture is only supported in GUI sessions; background sessions render")
    if source == "viewport" or (source == "auto" and not BACKGROUND):
        png, meta = _viewport_png(width, height)
    else:
        png, meta = _render_png(width, height)
        meta.update(width=width, height=height)
    meta["png_base64"] = base64.b64encode(png).decode("ascii")
    return meta


def checkpoint(label=None):
    key = f"ckpt{len(_checkpoints) + 1}"
    path = os.path.join(WORKDIR, f"{key}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, check_existing=False)
    _checkpoints[key] = path
    return {"checkpoint": key, "label": label}


def _open_mainfile(path):
    # Without allow_exec, scripts embedded in the file (registered text blocks,
    # Python drivers) must not run, whatever the auto-exec preference says.
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=ALLOW_EXEC)


def restore(checkpoint_id):
    path = _checkpoints.get(checkpoint_id)
    if path is None:
        raise BridgeError(f"unknown checkpoint {checkpoint_id!r}; known: {sorted(_checkpoints)}")
    _open_mainfile(path)
    # bpy.data.filepath now names the checkpoint copy; save() always takes an explicit path.
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
    _open_mainfile(os.path.abspath(filepath))
    return {"file": bpy.data.filepath, "objects": len(bpy.context.scene.objects)}


def _iter_operators():
    for module_name in dir(bpy.ops):
        module = getattr(bpy.ops, module_name)
        for op_name in dir(module):
            yield f"{module_name}.{op_name}", getattr(module, op_name).get_rna_type()


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
    _, rna = _resolve_operator(idname)
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
    if not isinstance(request, dict) or not isinstance(request.get("params", {}), dict):
        return wire.error_response(None, "BadRequest", "a request must be an object with an object 'params'")
    request_id = request.get("id")
    method = request.get("method")
    handler = HANDLERS.get(method)
    if handler is None:
        return wire.error_response(request_id, "UnknownMethod", f"unknown method {method!r}")
    try:
        response = {"id": request_id, "ok": True, "result": handler(**request.get("params", {}))}
    except Exception as exc:  # every failure goes back to the agent, the bridge keeps serving
        response = wire.error_response(request_id, type(exc).__name__, str(exc), traceback.format_exc())
    if not ALLOW_EXEC:
        turned_off = _disable_freestyle()  # before control returns to the event loop and its redraws
        if turned_off:
            note = f"Freestyle runs Python and needs allow_exec; it was turned off in scenes {turned_off}"
            return wire.report_side_effect(response, "FreestyleDisabled", note)
    return response


def _send_response(sock, response):
    try:
        frame = wire.encode_frame(response)
    except wire.FrameTooLarge as exc:
        frame = wire.encode_frame(wire.error_response(response.get("id"), "ResponseTooLarge", str(exc)))
    sock.sendall(frame)


def _next_request(sock):
    """Next request, or a ready-made error response for a well-framed but invalid payload."""
    try:
        return wire.recv_frame(sock), None
    except wire.InvalidPayload as exc:
        return None, wire.error_response(None, "BadRequest", str(exc))


def _serve_one(sock, request, rejected):
    """Answer one request; True when the client asked to quit."""
    if rejected is not None:
        _send_response(sock, rejected)
        return False
    if isinstance(request, dict) and request.get("method") == "quit":
        wire.send_frame(sock, {"id": request.get("id"), "ok": True, "result": {"quit": True}})
        return True
    _send_response(sock, handle(request))
    return False


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
                request, rejected = _next_request(sock)
            except wire.ConnectionClosed:
                return
            if _serve_one(sock, request, rejected):
                return
    finally:
        sock.close()


def serve_gui():
    sock = _connect()
    inbox = queue.Queue()

    def reader():
        # Only moves frames into the queue; all bpy access stays on the main thread.
        while True:
            try:
                inbox.put(_next_request(sock))
            except (wire.ProtocolError, OSError):
                inbox.put(None)
                return

    threading.Thread(target=reader, name="blender-agent-reader", daemon=True).start()

    def shutdown():
        sock.close()
        bpy.ops.wm.quit_blender()
        return None

    def drain():
        while True:
            try:
                item = inbox.get_nowait()
            except queue.Empty:
                return 0.02
            try:
                if item is None:  # client gone: do not leave an orphaned Blender window
                    return shutdown()
                if _serve_one(sock, *item):
                    return shutdown()
            except OSError:
                return shutdown()

    bpy.app.timers.register(drain, first_interval=0.0, persistent=True)


if BACKGROUND:
    serve_background()
else:
    serve_gui()
