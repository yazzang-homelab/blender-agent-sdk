import pytest

from blender_agent import RemoteError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _names(session):
    return {o["name"] for o in session.scene_graph()["objects"]}


def test_ping_reports_background_and_exec_policy(session):
    info = session.ping()
    assert info["pong"] is True
    assert info["background"] is True
    assert info["allow_exec"] is False
    assert info["blender_version"].startswith(("4.", "5."))


def test_operator_changes_scene_graph(session):
    before = _names(session)
    assert session.call_operator("mesh.primitive_uv_sphere_add", {"radius": 0.5, "location": [2, 0, 0]}) == {
        "result": ["FINISHED"]}
    added = _names(session) - before
    assert added == {"Sphere"}
    info = session.object_info("Sphere")
    assert info["location"] == [2.0, 0.0, 0.0]
    assert info["mesh"]["vertices"] > 0


def test_remote_error_carries_traceback_and_session_survives(session):
    with pytest.raises(RemoteError) as err:
        session.object_info("does-not-exist")
    assert err.value.type_name == "BridgeError"
    assert "does-not-exist" in err.value.message
    assert "Traceback" in err.value.remote_traceback
    assert session.ping()["pong"] is True


def test_unknown_operator_is_a_remote_error(session):
    with pytest.raises(RemoteError, match="unknown operator"):
        session.call_operator("mesh.no_such_operator")


def test_set_and_get_nested_property(session):
    session.call_operator("object.modifier_add", {"type": "BEVEL"})
    assert session.set_property("objects", "Cube", "modifiers['Bevel'].width", 0.25) == pytest.approx(0.25)
    assert session.get_property("objects", "Cube", "modifiers['Bevel'].width") == pytest.approx(0.25)
    assert session.set_property("objects", "Cube", "location", [1, 2, 3]) == [1.0, 2.0, 3.0]


def test_screenshot_is_png(session):
    png, meta = session.screenshot(160, 120)
    assert png.startswith(PNG_SIGNATURE)
    assert meta["method"] == "render"
    assert meta["temporary_camera"] is False


def test_cycles_screenshot_leaves_scene_settings_untouched(blender_bin):
    from blender_agent import BlenderSession

    with BlenderSession(blender_bin, env={"BLENDER_AGENT_RENDER_ENGINE": "CYCLES"}) as bl:
        bl.set_property("scenes", "Scene", "render.engine", "CYCLES")
        bl.set_property("scenes", "Scene", "cycles.samples", 77)
        bl.set_property("scenes", "Scene", "render.resolution_x", 1234)
        png, meta = bl.screenshot(64, 48)
        assert png.startswith(PNG_SIGNATURE) and meta["engine"] == "CYCLES"
        assert bl.get_property("scenes", "Scene", "cycles.samples") == 77
        assert bl.get_property("scenes", "Scene", "cycles.device") == "CPU"
        assert bl.get_property("scenes", "Scene", "render.resolution_x") == 1234


def test_render_failure_restores_scene_settings(blender_bin):
    from blender_agent import BlenderSession

    with BlenderSession(blender_bin, env={"BLENDER_AGENT_RENDER_ENGINE": "NO_SUCH_ENGINE"}) as bl:
        engine = bl.get_property("scenes", "Scene", "render.engine")
        with pytest.raises(RemoteError):
            bl.screenshot(64, 48)
        assert bl.get_property("scenes", "Scene", "render.engine") == engine
        assert bl.get_property("scenes", "Scene", "render.resolution_x") == 1920
        assert bl.scene_graph()["camera"] == "Camera"


def test_poll_failure_is_reported_with_mode(session):
    with pytest.raises(RemoteError, match=r"mesh.subdivide.poll\(\) failed .*mode='OBJECT'"):
        session.call_operator("mesh.subdivide")


def test_screenshot_without_camera_uses_temporary_camera(session):
    session.set_property("scenes", "Scene", "camera", None)
    assert session.scene_graph()["camera"] is None
    png, meta = session.screenshot(160, 120)
    assert png.startswith(PNG_SIGNATURE)
    assert meta["temporary_camera"] is True
    graph = session.scene_graph()
    assert graph["camera"] is None
    assert "blender_agent_tmp_cam" not in {o["name"] for o in graph["objects"]}


def test_checkpoint_restore_roundtrip(session):
    ckpt = session.checkpoint("clean")
    session.call_operator("object.select_all", {"action": "SELECT"})
    session.call_operator("object.delete")
    assert _names(session) == set()
    session.restore(ckpt)
    assert {"Cube", "Camera", "Light"} <= _names(session)


def test_restore_unknown_checkpoint(session):
    with pytest.raises(RemoteError, match="unknown checkpoint"):
        session.restore("ckpt999")


def test_undo_is_refused_in_background(session):
    with pytest.raises(RemoteError, match="no undo stack"):
        session.undo()


def test_exec_python_is_disabled_by_default(session):
    with pytest.raises(RemoteError, match="exec_python is disabled"):
        session.exec_python("print('hi')")


def test_exec_python_when_allowed(exec_session):
    out = exec_session.exec_python("print('hello'); result = sorted(o.name for o in bpy.data.objects)")
    assert out["stdout"] == "hello\n"
    assert out["result"] == ["Camera", "Cube", "Light"]


def test_search_and_describe_operator(session):
    found = session.search_operators("add cube", limit=5)
    assert "mesh.primitive_cube_add" in [op["idname"] for op in found["operators"]]
    desc = session.describe_operator("mesh.primitive_cube_add")
    assert "size" in {p["name"] for p in desc["properties"]}


def test_save_and_open(session, tmp_path):
    target = tmp_path / "scene.blend"
    session.call_operator("mesh.primitive_cone_add")
    session.save(target)
    assert target.exists()
    session.call_operator("object.select_all", {"action": "SELECT"})
    session.call_operator("object.delete")
    session.open_file(target)
    assert "Cone" in _names(session)
