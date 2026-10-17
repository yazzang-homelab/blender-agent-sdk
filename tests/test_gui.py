"""GUI-mode smoke test. Needs a display: run under ``xvfb-run -a pytest`` on headless machines.

CI sets BLENDER_AGENT_REQUIRE_GUI=1 so a missing display fails instead of skipping.
"""

import os

import pytest

from blender_agent import BlenderSession

HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
REQUIRED = os.environ.get("BLENDER_AGENT_REQUIRE_GUI") == "1"

pytestmark = pytest.mark.skipif(
    not HAS_DISPLAY and not REQUIRED,
    reason="GUI mode needs a display (DISPLAY or WAYLAND_DISPLAY); use xvfb-run",
)


def test_gui_session_viewport_and_undo(blender_bin):
    assert HAS_DISPLAY, "BLENDER_AGENT_REQUIRE_GUI=1 but no DISPLAY/WAYLAND_DISPLAY is set"
    with BlenderSession(blender_bin, background=False, timeout=120, startup_timeout=120) as bl:
        assert bl.ping()["background"] is False
        bl.call_operator("mesh.primitive_monkey_add")
        assert "Suzanne" in {o["name"] for o in bl.scene_graph()["objects"]}

        png, meta = bl.screenshot(320, 240, source="viewport")
        assert png.startswith(b"\x89PNG")
        assert meta["method"] == "viewport_offscreen"
        assert 0 < meta["width"] <= 320 and 0 < meta["height"] <= 240

        bl.undo()
        assert "Suzanne" not in {o["name"] for o in bl.scene_graph()["objects"]}

        ckpt = bl.checkpoint()
        bl.call_operator("mesh.primitive_cone_add")
        bl.restore(ckpt)  # wm.open_mainfile from inside the bpy.app.timers callback
        assert "Cone" not in {o["name"] for o in bl.scene_graph()["objects"]}
