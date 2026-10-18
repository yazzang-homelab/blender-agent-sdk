"""The MCP adapter, checked with the official ``mcp`` client and at the JSON-RPC level."""

import asyncio
import base64
import json
import sys

from mcp import ClientSession, StdioServerParameters, stdio_client

from blender_agent.mcp_server import PROTOCOL_VERSIONS, McpServer
from blender_agent.studio import Gallery, Studio


def _is_error(result):
    return getattr(result, "is_error", None) if hasattr(result, "is_error") else result.isError  # mcp 2.x / 1.x


def _run(coro):
    return asyncio.run(coro)


def test_official_client_drives_a_persistent_session(blender_bin, tmp_path):
    out = tmp_path / "gallery"

    async def scenario():
        params = StdioServerParameters(command=sys.executable,
                                       args=["-m", "blender_agent", "mcp", "--blender", blender_bin, "--out", str(out)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert {"scene_graph", "call_operator", "show", "gallery", "reset_scene"} <= names
                assert "exec_python" not in names

                added = await client.call_tool("call_operator", {"idname": "mesh.primitive_monkey_add"})
                assert not _is_error(added)
                graph = await client.call_tool("scene_graph", {})
                assert "Suzanne" in graph.content[0].text  # state survives between calls

                shown = await client.call_tool("show", {"label": "monkey", "width": 64, "height": 48})
                assert [c.type for c in shown.content] == ["text", "text", "image"]
                assert base64.b64decode(shown.content[2].data).startswith(b"\x89PNG")
                assert "gallery #1" in shown.content[1].text

                refused = await client.call_tool("call_operator", {"idname": "script.python_file_run",
                                                                   "params": {"filepath": "x.py"}})
                assert _is_error(refused) and "refused without allow_exec" in refused.content[0].text

                info = json.loads((await client.call_tool("gallery", {})).content[0].text)
                assert info["count"] == 1 and info["recent"][0]["label"] == "monkey"

                await client.call_tool("reset_scene", {})
                graph = await client.call_tool("scene_graph", {})
                assert "Suzanne" not in graph.content[0].text

    _run(scenario())
    assert (out / "shots" / "0001.png").exists()


def _server(tmp_path, allow_exec=False):
    return McpServer(Studio(Gallery(tmp_path), allow_exec=allow_exec))


def test_jsonrpc_edge_cases(tmp_path):
    server = _server(tmp_path)
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05"}})
    assert init["result"]["protocolVersion"] == "2024-11-05"
    unknown_version = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize",
                                     "params": {"protocolVersion": "1999-01-01"}})
    assert unknown_version["result"]["protocolVersion"] == PROTOCOL_VERSIONS[0]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"] == -32601
    assert server.handle_line("{broken")["error"]["code"] == -32700
    batch = server.handle_line(json.dumps([{"jsonrpc": "2.0", "id": 4, "method": "ping"},
                                           {"jsonrpc": "2.0", "method": "notifications/initialized"}]))
    assert batch == [{"jsonrpc": "2.0", "id": 4, "result": {}}]
    bad_tool = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "exec_python"}})
    assert bad_tool["result"]["isError"] is True  # not offered without allow_exec


def test_exec_python_is_offered_only_with_allow_exec(tmp_path):
    def names(server):
        return {t["name"] for t in server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]}

    assert "exec_python" not in names(_server(tmp_path / "a"))
    assert "exec_python" in names(_server(tmp_path / "b", allow_exec=True))
