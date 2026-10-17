import json
import os
from pathlib import Path

import pytest

from blender_agent import TOOLS, anthropic_tools, dispatch, openai_tools

GOLDEN = Path(__file__).parent / "golden"


def _check_golden(name, value):
    path = GOLDEN / name
    rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("UPDATE_GOLDEN"):
        path.write_text(rendered, encoding="utf-8")
    assert rendered == path.read_text(encoding="utf-8"), f"{name} changed; rerun with UPDATE_GOLDEN=1 if intended"


def test_openai_schema_golden():
    _check_golden("openai_tools.json", openai_tools(include_exec=True))


def test_anthropic_schema_golden():
    _check_golden("anthropic_tools.json", anthropic_tools(include_exec=True))


def test_exec_python_is_opt_in_for_schemas():
    assert "exec_python" not in {t["function"]["name"] for t in openai_tools()}
    assert "exec_python" not in {t["name"] for t in anthropic_tools()}


def test_every_tool_maps_to_a_bridge_method():
    # bridge.py imports bpy, so read its HANDLERS table statically.
    import ast

    import blender_agent.client as client

    tree = ast.parse(client.BRIDGE_SCRIPT.read_text(encoding="utf-8"))
    handlers = next(node.value for node in tree.body
                    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "HANDLERS")
    assert {t["name"] for t in TOOLS} <= {k.value for k in handlers.keys}


def test_dispatch_accepts_json_string_and_returns_image(session):
    outcome = dispatch(session, "screenshot", json.dumps({"width": 64, "height": 48}))
    assert outcome["ok"] is True
    assert outcome["image_png"].startswith(b"\x89PNG")
    assert "png_base64" not in outcome["result"]


def test_dispatch_returns_remote_errors_instead_of_raising(session):
    outcome = dispatch(session, "object_info", {"name": "missing"})
    assert outcome == {"ok": False, "error": "BridgeError: no object named 'missing'", "image_png": None}


def test_dispatch_rejects_unknown_tool_and_bad_arguments(session):
    assert dispatch(session, "rm_rf", {})["ok"] is False
    bad = dispatch(session, "object_info", {"nam": "Cube"})
    assert bad["ok"] is False
    assert "unexpected keyword" in bad["error"] or "missing" in bad["error"]


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t["name"])
def test_required_parameters_exist(tool):
    params = tool["parameters"]
    assert params["type"] == "object"
    assert set(params["required"]) <= set(params["properties"])
