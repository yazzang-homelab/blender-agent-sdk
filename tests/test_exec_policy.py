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
    ("wm.previews_batch_generate", {"directory": "/tmp/", "use_scenes": True}),
    ("wm.read_homefile", {"app_template": "Video_Editing"}),
    ("render.preset_add", {"name": "x"}),
    *[(idname, {"settings": [{"name": "label", "value": "__import__('os').getpid()"}]}) for idname in (
        "node.add_node", "node.swap_node", "node.add_zone", "node.swap_zone", "node.add_simulation_zone",
        "node.add_repeat_zone", "node.add_closure_zone", "node.add_foreach_geometry_element_zone",
        "node.add_empty_group", "node.swap_empty_group", "node.add_typed_bundle", "node.swap_typed_bundle")],
    ("wm.open_mainfile", {"filepath": "/tmp/x.blend", "use_scripts": True}),
    ("wm.open_mainfile", {"filepath": "/tmp/x.blend", "load_ui": True}),
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


def test_invoked_render_jobs_are_refused(session):
    with pytest.raises(RemoteError, match="render job that outlives the request"):
        session.call_operator("render.render", execution_context="INVOKE_DEFAULT")
    with pytest.raises(RemoteError, match="render job that outlives the request"):
        session.call_operator("node.render_changed")


def test_ordinary_operators_still_work(session):
    assert session.call_operator("mesh.primitive_cube_add")["result"] == ["FINISHED"]
    assert session.call_operator("object.select_pattern", {"pattern": "Cube*"})["result"] == ["FINISHED"]


# --enable-autoexec turns Blender's auto-exec preference on, so these tests fail if the bridge stops
# forcing use_scripts=False: without it, wm.open_mainfile would fall back to that preference.
AUTOEXEC_ON = ["--enable-autoexec"]


_LOADERS = {
    "wm.open_mainfile": lambda bl, blend: bl.call_operator("wm.open_mainfile", {"filepath": str(blend)}),
    "open_file": lambda bl, blend: bl.open_file(blend),
    "restore": lambda bl, blend: bl.restore(bl.checkpoint()),  # the session planted it itself
}


@pytest.mark.parametrize("loader", sorted(_LOADERS))
def test_file_loads_do_not_run_embedded_scripts(blender_bin, session, tmp_path, loader):
    # A fresh session per load path: Blender clears its auto-exec flag after a load with
    # use_scripts=False, which would let a later load pass even without the bridge's forcing.
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    with BlenderSession(blender_bin, extra_args=AUTOEXEC_ON) as bl:
        if loader == "restore":
            _plant_registered_text(bl, marker, tmp_path / "copy.blend")
        _LOADERS[loader](bl, blend)
        assert bl.get_property("texts", "Text", "use_module") is True  # the planted file did load
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


def test_animation_path_update_cannot_eval_planted_data_path(blender_bin, tmp_path):
    marker = tmp_path / "marker"
    payload = f"location, open({str(marker)!r}, 'w').write('ran')"
    for allow_exec in (False, True):
        with BlenderSession(blender_bin, allow_exec=allow_exec) as bl:
            bl.call_operator("anim.keyframe_insert_by_name", {"type": "Location"})
            bl.set_property("actions", "CubeAction", "layers[0].strips[0].channelbags[0].fcurves[0].data_path", payload)
            if allow_exec:  # positive control: the operator does eval() the planted path
                with pytest.raises(RemoteError):  # the mangled path fails after eval() ran it
                    bl.call_operator("anim.update_animated_transform_constraints")
                assert marker.read_text() == "ran"
            else:
                with pytest.raises(RemoteError, match="refused without allow_exec"):
                    bl.call_operator("anim.update_animated_transform_constraints")
                assert not marker.exists()


_FREESTYLE_SCRIPT_MODE = """
text = bpy.data.texts.new("style.py")
text.write(f"open({MARKER!r}, 'w').write('ran')")
settings = bpy.context.view_layer.freestyle_settings
settings.mode = "SCRIPT"
bpy.ops.scene.freestyle_module_add()
settings.modules[-1].script = text
"""
# EDITOR mode evaluates "__import__('parameter_editor').process('<layer>', '<line set>')" with only
# quotes escaped (FRS_freestyle.cpp:165-188), so a backslash in a name ends the string literal
# (the payload itself must avoid single quotes, which do get escaped).
# Names are limited to 63 bytes, so the injected expression runs a text block's contents.
_FREESTYLE_EDITOR_MODE = """
bpy.data.texts.new("p").write(f"open({MARKER!r}, 'w').write('ran')")
settings = bpy.context.view_layer.freestyle_settings
settings.mode = "EDITOR"
settings.linesets[0].name = "\\\\', exec(__import__(\\"bpy\\").data.texts[\\"p\\"].as_string()))#"
"""


def _build_freestyle_file(exec_session, marker, blend, mode):
    setup = _FREESTYLE_SCRIPT_MODE if mode == "SCRIPT" else _FREESTYLE_EDITOR_MODE
    exec_session.exec_python(
        f"MARKER = {str(marker)!r}\n{setup}\n"
        "scene = bpy.context.scene\n"
        "scene.render.use_freestyle = True\n"
        "scene.render.engine = 'CYCLES'\n"
        "scene.cycles.samples = 1\n"
        "scene.render.resolution_x, scene.render.resolution_y = 32, 24\n"
        f"bpy.ops.wm.save_as_mainfile(filepath={str(blend)!r})")


def _freestyle_on(bl):
    return bl.get_property("scenes", "Scene", "render.use_freestyle")


@pytest.mark.parametrize("mode", ["SCRIPT", "EDITOR"])
def test_freestyle_is_kept_off_without_exec(blender_bin, exec_session, tmp_path, mode):
    marker, blend = tmp_path / "marker", tmp_path / "freestyle.blend"
    _build_freestyle_file(exec_session, marker, blend, mode)
    with BlenderSession(blender_bin, blend_file=blend) as bl:  # launch file: off before the first redraw
        assert _freestyle_on(bl) is False
        bl.screenshot(32, 24)
        bl.call_operator("render.render")
    with BlenderSession(blender_bin) as bl:
        with pytest.raises(RemoteError, match="turned off in scenes") as err:
            bl.open_file(blend)
        assert err.value.type_name == "FreestyleDisabled"
        assert _freestyle_on(bl) is False
        for path in ("render.use_freestyle", "view_layers[0].use_freestyle"):
            with pytest.raises(RemoteError, match="refused without allow_exec: Freestyle"):
                bl.set_property("scenes", "Scene", path, True)
        assert _freestyle_on(bl) is False
        bl.call_operator("render.render")
    assert not marker.exists()
    # Positive control: the same file runs the payload when it renders with Freestyle on, even
    # though it was opened with use_scripts=False.
    exec_session.call_operator("wm.open_mainfile", {"filepath": str(blend), "use_scripts": False})
    exec_session.exec_python("bpy.ops.render.render()")
    assert marker.read_text() == "ran"


def test_opened_files_do_not_bring_their_ui(session, blender_bin, tmp_path):
    """load_ui is forced off, so a file cannot install, e.g., a sequencer preview that renders on redraw."""
    blend = tmp_path / "ui.blend"
    session.set_property("workspaces", "Layout", "name", "Planted")
    session.save(blend)
    with BlenderSession(blender_bin) as bl:
        bl.call_operator("wm.open_mainfile", {"filepath": str(blend)})  # load_ui omitted
        assert bl.get_property("workspaces", "Layout", "name") == "Layout"


def test_scene_previews_do_not_render_freestyle(blender_bin, exec_session, tmp_path):
    """wm.previews_batch_generate renders scenes with their own settings in a child Blender."""
    marker, blend = tmp_path / "marker", tmp_path / "freestyle.blend"
    _build_freestyle_file(exec_session, marker, blend, "SCRIPT")
    params = {"directory": f"{tmp_path}/", "files": [{"name": blend.name}]}
    with BlenderSession(blender_bin) as bl:
        bl.call_operator("wm.previews_batch_generate", params)  # use_scenes forced to False
    assert not marker.exists()
    # Positive control: with scene previews on, the child Blender does run the Freestyle script.
    exec_session.call_operator("wm.previews_batch_generate", {**params, "use_scenes": True})
    assert marker.read_text() == "ran"


def test_freestyle_cannot_be_animated_or_driven(exec_session):
    """Why turning it off after each request is enough: nothing else can switch it back on."""
    for call in ("keyframe_insert", "driver_add"):
        with pytest.raises(RemoteError, match="not animatable"):
            exec_session.exec_python(f"bpy.context.scene.{call}('render.use_freestyle')")


def test_preview_generation_cannot_run_embedded_scripts(session, tmp_path):
    marker, blend = tmp_path / "marker", tmp_path / "planted.blend"
    _plant_registered_text(session, marker, blend)
    for idname in ("wm.previews_batch_generate", "wm.previews_batch_clear"):
        params = {"directory": f"{tmp_path}/", "files": [{"name": blend.name}]}
        with pytest.raises(RemoteError, match="use_trusted=True"):
            session.call_operator(idname, {**params, "use_trusted": True})
        session.call_operator(idname, params)  # forced to use_trusted=False
    assert not marker.exists()
