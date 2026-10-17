"""Agent tool definitions for function-calling LLM APIs (no MCP).

``TOOLS`` is the single source of truth. ``openai_tools()`` and
``anthropic_tools()`` render it for the respective APIs, and ``dispatch()``
executes a tool call against a :class:`~blender_agent.client.BlenderSession`.
"""

import base64
import json

from .client import RemoteError, RequestTooLarge

_STR = {"type": "string"}
_INT = {"type": "integer"}

TOOLS = [
    {
        "name": "scene_graph",
        "description": "List the current scene: every object with type, transform, dimensions, "
                       "visibility, selection and collections, plus active object, camera, mode and render engine.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "object_info",
        "description": "Detailed state of one object: transform, world bounding box, modifiers, "
                       "materials, mesh counts or light/camera settings.",
        "parameters": {"type": "object", "properties": {"name": {**_STR, "description": "Object name."}},
                       "required": ["name"]},
    },
    {
        "name": "screenshot",
        "description": "Look at the scene. Returns a PNG image. In background sessions this renders from the "
                       "scene camera (a temporary camera framing all visible objects is used when none exists); "
                       "in GUI sessions it captures the 3D viewport, keeping the viewport's aspect ratio "
                       "(width/height are then an upper bound).",
        "parameters": {"type": "object", "properties": {
            "width": {**_INT, "description": "Image width in pixels (default 640)."},
            "height": {**_INT, "description": "Image height in pixels (default 480)."},
            "source": {"type": "string", "enum": ["auto", "render", "viewport"],
                       "description": "auto = viewport in GUI sessions, render in background sessions."},
        }, "required": []},
    },
    {
        "name": "search_operators",
        "description": "Search Blender's operators (bpy.ops) by keywords, e.g. 'add cube' or 'bevel'. "
                       "Use before call_operator when you do not know the exact idname.",
        "parameters": {"type": "object", "properties": {
            "query": {**_STR, "description": "Space-separated keywords; all must match."},
            "limit": {**_INT, "description": "Maximum results (default 20)."},
        }, "required": ["query"]},
    },
    {
        "name": "describe_operator",
        "description": "Show an operator's parameters with types and enum values.",
        "parameters": {"type": "object", "properties": {
            "idname": {**_STR, "description": "Operator idname such as 'mesh.primitive_cube_add'."}},
            "required": ["idname"]},
    },
    {
        "name": "call_operator",
        "description": "Run a Blender operator (bpy.ops.<idname>) with keyword parameters, inside a context "
                       "override for the given editor area (default VIEW_3D).",
        "parameters": {"type": "object", "properties": {
            "idname": {**_STR, "description": "Operator idname such as 'mesh.primitive_cube_add'."},
            "params": {"type": "object", "description": "Operator keyword arguments."},
            "area_type": {**_STR, "description": "Editor area to run in, e.g. VIEW_3D, NODE_EDITOR."},
        }, "required": ["idname"]},
    },
    {
        "name": "get_property",
        "description": "Read an RNA property of a datablock, e.g. collection='objects', name='Cube', "
                       "path='location' or path=\"modifiers['Bevel'].width\".",
        "parameters": {"type": "object", "properties": {
            "collection": {**_STR, "description": "bpy.data collection: objects, meshes, materials, scenes, ..."},
            "name": {**_STR, "description": "Datablock name."},
            "path": {**_STR, "description": "RNA data path relative to the datablock."},
        }, "required": ["collection", "name", "path"]},
    },
    {
        "name": "set_property",
        "description": "Assign an RNA property of a datablock. Vectors are JSON arrays.",
        "parameters": {"type": "object", "properties": {
            "collection": {**_STR, "description": "bpy.data collection: objects, meshes, materials, scenes, ..."},
            "name": {**_STR, "description": "Datablock name."},
            "path": {**_STR, "description": "RNA data path relative to the datablock."},
            "value": {"description": "New value (number, string, boolean or array)."},
        }, "required": ["collection", "name", "path", "value"]},
    },
    {
        "name": "checkpoint",
        "description": "Snapshot the whole file so it can be restored later. Returns a checkpoint id.",
        "parameters": {"type": "object", "properties": {"label": {**_STR, "description": "Optional note."}},
                       "required": []},
    },
    {
        "name": "restore",
        "description": "Restore the file to a checkpoint taken earlier in this session.",
        "parameters": {"type": "object", "properties": {"checkpoint_id": _STR}, "required": ["checkpoint_id"]},
    },
    {
        "name": "save",
        "description": "Save the current file as a .blend at the given path.",
        "parameters": {"type": "object", "properties": {"filepath": _STR}, "required": ["filepath"]},
    },
    {
        "name": "exec_python",
        "description": "Run Python inside Blender with `bpy` imported. Printed output is returned; assign to "
                       "`result` to return a value. Only available when the session allows it.",
        "parameters": {"type": "object", "properties": {"code": _STR}, "required": ["code"]},
    },
]

_BY_NAME = {tool["name"]: tool for tool in TOOLS}


def _selected(include_exec):
    return [t for t in TOOLS if include_exec or t["name"] != "exec_python"]


def openai_tools(include_exec=False):
    """Tool list for the OpenAI Chat Completions ``tools`` parameter (nested ``function`` shape)."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["parameters"]}}
            for t in _selected(include_exec)]


def anthropic_tools(include_exec=False):
    """Tool list for the Anthropic Messages API ``tools`` parameter."""
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in _selected(include_exec)]


def dispatch(session, name, arguments):
    """Execute one tool call.

    ``arguments`` must be a dict or a JSON string encoding an object (as OpenAI returns
    it). Returns ``{"ok": bool, "result"|"error": ..., "image_png": bytes | None}``.
    Invalid tool calls, oversized requests (:class:`~blender_agent.client.RequestTooLarge`)
    and errors raised inside Blender are returned, not raised, so the agent can read and
    correct them; :class:`~blender_agent.client.SessionLost` still propagates.
    """
    tool = _BY_NAME.get(name)
    if tool is None:
        return _failed(f"unknown tool {name!r}")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return _failed(f"arguments for {name} are not valid JSON: {exc}")
    if not isinstance(arguments, dict):
        return _failed(f"arguments for {name} must be a JSON object, got {type(arguments).__name__}")
    schema = tool["parameters"]
    unknown = sorted(set(arguments) - set(schema["properties"]))
    missing = sorted(set(schema["required"]) - set(arguments))
    if unknown or missing:
        return _failed(f"bad arguments for {name}: unknown {unknown}, missing {missing}")
    try:
        if name == "screenshot":
            png, meta = session.screenshot(**arguments)
            return {"ok": True, "result": meta, "image_png": png}
        return {"ok": True, "result": session.request(name, arguments), "image_png": None}
    except (RemoteError, RequestTooLarge) as exc:
        return _failed(str(exc))


def _failed(message):
    return {"ok": False, "error": message, "image_png": None}


def result_text(outcome):
    """Compact JSON text of a dispatch outcome, suitable as a tool-result message."""
    body = {"ok": outcome["ok"], **({"result": outcome["result"]} if outcome["ok"] else {"error": outcome["error"]})}
    return json.dumps(body, ensure_ascii=False, default=str)


def image_base64(outcome):
    png = outcome.get("image_png")
    return base64.b64encode(png).decode("ascii") if png else None
