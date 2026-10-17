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
    ("wm.path_open", {"filepath": "/tmp"}),
    ("image.external_edit", {"filepath": "/tmp/x.png"}),
    ("anim.keying_set_export", {"filepath": "/tmp/x.py"}),
    ("asset.open_containing_blend_file", {}),
    ("wm.context_toggle", {"data_path": "scene.use_gravity"}),
    ("wm.previews_batch_generate", {"directory": "/tmp/", "use_trusted": True}),
    ("render.preset_add", {"name": "x"}),
    *[(idname, {"settings": [{"name": "label", "value": "__import__('os').getpid()"}]}) for idname in (
        "node.add_node", "node.swap_node", "node.add_zone", "node.swap_zone", "node.add_simulation_zone",
        "node.add_repeat_zone", "node.add_closure_zone", "node.add_foreach_geometry_element_zone",
        "node.add_empty_group", "node.swap_empty_group", "node.add_typed_bundle", "node.swap_typed_bundle")],
    ("wm.open_mainfile", {"filepath": "/tmp/x.blend", "use_scripts": True}),
])
def test_code_running_operators_are_refused(session, idname, params):
    with pytest.raises(RemoteError, match="refused without allow_exec"):
        session.call_operator(idname, params)
    assert session.ping()["pong"] is True


def test_every_node_setting_operator_is_refused(exec_session, session):
    """Every operator with a NodeSetting collection eval()s it, including ones added later."""
    found = exec_session.exec_python(
        "result = sorted(f'{m}.{o}' for m in dir(bpy.ops) for o in dir(getattr(bpy.ops, m))"
        " if (s := getattr(getattr(bpy.ops, m), o).get_rna_type().properties.get('settings')) is not None"
        " and s.type == 'COLLECTION' and s.fixed_type.identifier == 'NodeSetting')")["result"]
    assert len(found) == 12
    for idname in found:
        with pytest.raises(RemoteError, match="refused without allow_exec"):
            session.call_operator(idname, {"settings": [{"name": "label", "value": "1"}]})


def test_ordinary_operators_still_work(session):
    assert session.call_operator("mesh.primitive_cube_add")["result"] == ["FINISHED"]
    assert session.call_operator("object.select_pattern", {"pattern": "Cube*"})["result"] == ["FINISHED"]


# --enable-autoexec turns Blender's auto-exec preference on, so these tests fail if the bridge stops
# forcing use_scripts=False: without it, wm.open_mainfile would fall back to that preference.
AUTOEXEC_ON = ["--enable-autoexec"]


def test_file_loads_do_not_run_embedded_scripts(blender_bin, session, tmp_path):
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    with BlenderSession(blender_bin, extra_args=AUTOEXEC_ON) as bl:
        bl.call_operator("wm.open_mainfile", {"filepath": str(blend)})  # use_scripts omitted
        assert bl.get_property("texts", "Text", "use_module") is True  # the planted file did load
        bl.open_file(blend)
        bl.restore(bl.checkpoint())
    assert not marker.exists()


def test_embedded_scripts_run_when_the_bridge_does_not_intervene(blender_bin, tmp_path):
    """Positive control for the test above: same Blender flags, exec allowed, use_scripts omitted."""
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    with BlenderSession(blender_bin, allow_exec=True, extra_args=AUTOEXEC_ON) as bl:
        _plant_registered_text(bl, marker, blend)
        bl.call_operator("wm.open_mainfile", {"filepath": str(blend)})
    assert marker.read_text() == "ran"


def test_disable_autoexec_precedes_the_launch_file(blender_bin, monkeypatch):
    """Blender applies --disable-autoexec only to files that come after it on the command line."""
    seen = []

    def capture(cmd, **kwargs):
        seen.append(cmd)
        raise OSError("captured")

    monkeypatch.setattr("blender_agent.client.subprocess.Popen", capture)
    for allow_exec in (False, True):
        with pytest.raises(OSError, match="captured"):
            BlenderSession(blender_bin, blend_file="scene.blend", allow_exec=allow_exec).start()
    denied, allowed = seen
    assert denied.index("--disable-autoexec") < denied.index("scene.blend")
    assert "--disable-autoexec" not in allowed


def test_preview_generation_cannot_run_embedded_scripts(session, tmp_path):
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    for idname in ("wm.previews_batch_generate", "wm.previews_batch_clear"):
        params = {"directory": f"{tmp_path}/", "files": [{"name": blend.name}]}
        with pytest.raises(RemoteError, match="use_trusted=True"):
            session.call_operator(idname, {**params, "use_trusted": True})
        session.call_operator(idname, params)  # forced to use_trusted=False
    assert not marker.exists()
