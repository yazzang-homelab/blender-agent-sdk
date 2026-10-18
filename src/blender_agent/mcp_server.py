"""MCP adapter: the SDK's agent tools over the Model Context Protocol (stdio transport).

``blender-agent mcp`` lets MCP hosts (Claude Code, Claude Desktop, Cursor, GJC, ...) drive
one Blender session that lives as long as the server. It is a thin layer over
:class:`~blender_agent.studio.Studio`: the tools, their schemas and the exec policy are the
SDK's own, and the server speaks JSON-RPC 2.0 over stdin/stdout with the standard
library only (no ``mcp`` package needed).
"""

import base64
import json
import sys
import traceback

from . import __version__
from .tools import TOOLS, result_text

__all__ = ["McpServer", "PROTOCOL_VERSIONS"]

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first

_SHOW = {
    "name": "show",
    "description": "Render the scene, store it in the session gallery (where the user follows along) and return "
                   "the image. Call it after every meaningful change and describe what changed in `label`.",
    "parameters": {"type": "object", "properties": {
        "label": {"type": "string", "description": "What this image shows, e.g. 'added red hat'."},
        "width": {"type": "integer"}, "height": {"type": "integer"},
        "source": {"type": "string", "enum": ["auto", "render", "viewport"]}}, "required": []},
}
_RESET = {
    "name": "reset_scene",
    "description": "Throw the scene away and start a fresh Blender (factory startup). Unsaved work is lost.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_GALLERY = {
    "name": "gallery",
    "description": "Where the user can see the session's images: gallery folder, latest image path, web URL if "
                   "served, and the most recent entries.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

_INSTRUCTIONS = (
    "You control a live Blender session. Inspect with scene_graph/object_info, find operators with "
    "search_operators/describe_operator, act with call_operator/set_property, checkpoint before risky steps. "
    "After each meaningful change call `show` with a short label: the image is saved to the user's gallery "
    "(see the `gallery` tool) and returned to you, so check it before claiming success.")


class McpServer:
    def __init__(self, studio, gallery_url=None):
        self.studio = studio
        self.gallery_url = gallery_url
        exec_ok = studio.options["allow_exec"]
        self.tools = [t for t in TOOLS if exec_ok or t["name"] != "exec_python"] + [_SHOW, _RESET, _GALLERY]

    # ------------------------------------------------------------- JSON-RPC

    def serve(self, stdin=None, stdout=None):
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        try:
            for line in stdin:
                if not line.strip():
                    continue
                reply = self.handle_line(line)
                if reply is not None:
                    stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
                    stdout.flush()
        finally:
            self.studio.close()

    def handle_line(self, line):
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            return _error(None, -32700, f"parse error: {exc}")
        if isinstance(message, list):  # JSON-RPC batch (2025-03-26)
            replies = [r for r in (self.handle(m) for m in message) if r is not None]
            return replies or None
        return self.handle(message)

    def handle(self, message):
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, -32600, "invalid request")
        if "method" not in message:
            return None  # a response to something we never send
        request_id = message.get("id")
        is_notification = "id" not in message
        try:
            result = self._dispatch(message["method"], message.get("params") or {})
        except _RpcError as exc:
            return None if is_notification else _error(request_id, exc.code, exc.message)
        except Exception as exc:  # report, keep serving
            traceback.print_exc(file=sys.stderr)
            return None if is_notification else _error(request_id, -32603, f"{type(exc).__name__}: {exc}")
        return None if is_notification else {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _dispatch(self, method, params):
        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return {"protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "blender-agent", "version": __version__},
                    "instructions": _INSTRUCTIONS}
        if method == "ping":
            return {}
        if method.startswith("notifications/"):
            return {}
        if method == "tools/list":
            return {"tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["parameters"]}
                              for t in self.tools]}
        if method == "tools/call":
            return self.call_tool(params.get("name"), params.get("arguments") or {})
        raise _RpcError(-32601, f"method not found: {method}")

    # ------------------------------------------------------------- tools

    def call_tool(self, name, arguments):
        if name not in {t["name"] for t in self.tools}:
            return _tool_result(f"unknown tool {name!r}", error=True)
        if not isinstance(arguments, dict):
            return _tool_result("arguments must be an object", error=True)
        if name == "reset_scene":
            return _tool_result(json.dumps({"ok": True, "result": self.studio.reset()}))
        if name == "gallery":
            return _tool_result(json.dumps(self.gallery_info(), ensure_ascii=False))
        if name == "show":
            label = arguments.get("label", "")
            shot_args = {k: v for k, v in arguments.items() if k != "label"}
            outcome = self.studio.run("screenshot", shot_args, label=label or "show")
        else:
            outcome = self.studio.run(name, arguments)
        content = [{"type": "text", "text": result_text(outcome)}]
        if outcome.get("image_png"):
            shot = outcome["shot"]
            where = f"Saved as {shot['path']} (gallery #{shot['n']})"
            if self.gallery_url:
                where += f"; the user sees it at {self.gallery_url}"
            content.append({"type": "text", "text": where})
            content.append({"type": "image", "mimeType": "image/png",
                            "data": base64.b64encode(outcome["image_png"]).decode("ascii")})
        return {"content": content, "isError": not outcome["ok"]}

    def gallery_info(self):
        gallery = self.studio.gallery
        entries = gallery.entries
        return {"folder": str(gallery.dir), "index_html": str(gallery.dir / "index.html"),
                "latest_png": str(gallery.dir / "latest.png") if entries else None,
                "url": self.gallery_url, "count": len(entries),
                "recent": [{"n": e["n"], "label": e["label"], "time": e["time"]} for e in entries[-5:]]}


class _RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(text, error=False):
    return {"content": [{"type": "text", "text": text}], "isError": error}
