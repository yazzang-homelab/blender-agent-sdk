"""Without allow_exec, no tool may run agent-controlled Python inside Blender."""

import pytest

from blender_agent import BlenderSession, RemoteError


def _marker_code(marker):
    return f"open({str(marker)!r}, 'w').write('ran')"


def _plant_registered_text(session, marker, blend):
    """A .blend whose text block runs on load when scripts are allowed (use_module)."""
    session.call_operator("text.new")
    session.set_property("texts", "Text", "lines[0].body", _marker_code(marker))
    session.set_property("texts", "Text", "use_module", True)
    session.save(blend)


@pytest.mark.parametrize("idname, params", [
    ("script.python_file_run", {"filepath": "/tmp/x.py"}),
    ("script.reload", {}),
    ("text.run_script", {}),
    ("console.execute", {}),
    ("preferences.addon_enable", {"module": "io_scene_fbx"}),
    ("extensions.repo_sync", {}),
    ("wm.context_set_value", {"data_path": "scene.frame_current", "value": "__import__('os').getpid()"}),
    ("wm.properties_edit_value", {"data_path": "object", "property_name": "x", "eval_string": "1"}),
    ("wm.url_open", {"url": "https://example.com"}),
    ("render.preset_add", {"name": "x"}),
    ("node.add_node", {"type": "ShaderNodeMath", "settings": [{"name": "operation", "value": "'ADD'"}]}),
    ("wm.open_mainfile", {"filepath": "/tmp/x.blend", "use_scripts": True}),
])
def test_code_running_operators_are_refused(session, idname, params):
    with pytest.raises(RemoteError, match="refused without allow_exec"):
        session.call_operator(idname, params)
    assert session.ping()["pong"] is True


def test_ordinary_operators_still_work(session):
    assert session.call_operator("mesh.primitive_cube_add")["result"] == ["FINISHED"]
    assert session.call_operator("object.select_pattern", {"pattern": "Cube*"})["result"] == ["FINISHED"]


def test_open_mainfile_cannot_run_embedded_text_block(session, tmp_path):
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    # use_scripts omitted: the bridge forces False instead of using the auto-exec preference.
    session.call_operator("wm.open_mainfile", {"filepath": str(blend)})
    session.open_file(blend)
    ckpt = session.checkpoint()
    session.restore(ckpt)
    assert not marker.exists()


def test_blend_file_given_at_launch_does_not_autoexec(blender_bin, session, tmp_path):
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    with BlenderSession(blender_bin, blend_file=blend) as bl:
        assert bl.get_property("texts", "Text", "use_module") is True  # the planted file did load
    assert not marker.exists()


def test_same_chain_runs_when_exec_is_allowed(blender_bin, tmp_path):
    """Proves the regression test above would catch the bypass."""
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    with BlenderSession(blender_bin, allow_exec=True) as bl:
        _plant_registered_text(bl, marker, blend)
        bl.call_operator("wm.open_mainfile", {"filepath": str(blend), "use_scripts": True})
    assert marker.read_text() == "ran"
