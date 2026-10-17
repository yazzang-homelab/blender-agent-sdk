import os
import signal
import tempfile
import time

import pytest

from blender_agent import BlenderSession, RemoteError, RequestTooLarge, SessionLost, dispatch


def _started_with_checkpoint(blender_bin, **kwargs):
    bl = BlenderSession(blender_bin, **kwargs).start()
    bl.checkpoint()  # puts a .blend into the session directory
    return bl, bl._tmpdir


def test_hang_times_out_kills_blender_and_cleans_up(blender_bin):
    bl, tmpdir = _started_with_checkpoint(blender_bin, allow_exec=True, timeout=60)
    pid = bl.info["pid"]
    started = time.monotonic()
    with pytest.raises(SessionLost, match="timed out"):
        bl.exec_python("import time; time.sleep(60)", timeout=2)
    assert time.monotonic() - started < 15
    assert not bl.alive
    with pytest.raises(OSError):
        os.kill(pid, 0)  # the process is gone
    assert not os.path.exists(tmpdir)
    with pytest.raises(SessionLost):
        bl.ping()
    bl.close()


def test_crash_inside_blender_raises_session_lost_with_exit_code(blender_bin):
    bl, tmpdir = _started_with_checkpoint(blender_bin, allow_exec=True)
    with pytest.raises(SessionLost, match=r"exit code 3"):
        bl.exec_python("import os; os._exit(3)")
    assert not bl.alive
    assert not os.path.exists(tmpdir)
    bl.close()


def test_external_kill_raises_session_lost(blender_bin):
    bl, tmpdir = _started_with_checkpoint(blender_bin)
    os.kill(bl.info["pid"], signal.SIGKILL)
    time.sleep(0.5)
    with pytest.raises(SessionLost):
        bl.ping()
    assert not os.path.exists(tmpdir)
    bl.close()


def test_normal_close_removes_session_directory(blender_bin):
    bl, tmpdir = _started_with_checkpoint(blender_bin)
    bl.screenshot(32, 24)
    bl.close()
    assert not os.path.exists(tmpdir)
    bl.close()  # idempotent


def test_startup_failure_reports_exit_code_and_log(blender_bin):
    bl = BlenderSession(blender_bin, blend_file="/nonexistent/file.blend", startup_timeout=60)
    with pytest.raises(SessionLost, match=r"exited with code 1 during startup") as err:
        bl.start()
    assert "Blender log" in str(err.value)
    assert not bl.alive
    assert bl._tmpdir is None


def test_launch_failure_releases_everything(blender_bin, monkeypatch):
    created = []
    real_mkdtemp = tempfile.mkdtemp

    def tracking_mkdtemp(*args, **kwargs):
        created.append(real_mkdtemp(*args, **kwargs))
        return created[-1]

    def failing_popen(*args, **kwargs):
        raise OSError("simulated exec failure")

    monkeypatch.setattr("blender_agent.client.tempfile.mkdtemp", tracking_mkdtemp)
    monkeypatch.setattr("blender_agent.client.subprocess.Popen", failing_popen)
    bl = BlenderSession(blender_bin)
    with pytest.raises(OSError, match="simulated exec failure"):
        bl.start()
    assert created and not os.path.exists(created[0])
    assert bl._log is None


def test_oversized_response_is_a_remote_error(exec_session):
    with pytest.raises(RemoteError) as err:
        exec_session.exec_python("result = 'x' * (65 * 1024 * 1024)")
    assert err.value.type_name == "ResponseTooLarge"
    assert exec_session.ping()["pong"] is True


def test_oversized_request_is_not_sent_and_session_survives(session):
    with pytest.raises(RequestTooLarge, match="not sent"):
        session.call("ping", junk="x" * (65 * 1024 * 1024))
    assert session.ping()["pong"] is True
    outcome = dispatch(session, "object_info", {"name": "x" * (65 * 1024 * 1024)})
    assert outcome["ok"] is False and "not sent" in outcome["error"]
    assert session.ping()["pong"] is True


def test_malformed_frames_from_a_raw_peer_get_errors_not_a_crash(session):
    from blender_agent import protocol as wire

    sock = session._sock
    payload = b"{not json"
    sock.sendall(len(payload).to_bytes(4, "big") + payload)
    assert wire.recv_frame(sock)["error"]["type"] == "BadRequest"
    wire.send_frame(sock, [1, 2, 3])
    assert wire.recv_frame(sock)["error"]["type"] == "BadRequest"
    assert session.ping()["pong"] is True
