"""GUI-mode smoke test. Needs a display: run under ``xvfb-run -a pytest`` on headless machines."""

import os

import pytest

from blender_agent import BlenderSession

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")),
    reason="GUI mode needs a display (DISPLAY or WAYLAND_DISPLAY); use xvfb-run",
)


def test_gui_session_viewport_and_undo(blender_bin):
    with BlenderSession(blender_bin, background=False, timeout=120, startup_timeout=120) as bl:
        assert bl.ping()["background"] is False
        bl.call_operator("mesh.primitive_monkey_add")
        assert "Suzanne" in {o["name"] for o in bl.scene_graph()["objects"]}

        png, meta = bl.screenshot(320, 240, source="viewport")
        assert png.startswith(b"\x89PNG")
        assert meta["method"] == "viewport_offscreen"

        bl.undo()
        assert "Suzanne" not in {o["name"] for o in bl.scene_graph()["objects"]}
