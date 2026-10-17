import os
import signal
import time

import pytest

from blender_agent import BlenderSession, SessionLost


def test_hang_times_out_kills_blender_and_raises(blender_bin):
    bl = BlenderSession(blender_bin, allow_exec=True, timeout=60).start()
    pid = bl.info["pid"]
    started = time.monotonic()
    with pytest.raises(SessionLost, match="timed out"):
        bl.exec_python("import time; time.sleep(60)", timeout=2)
    assert time.monotonic() - started < 15
    assert not bl.alive
    with pytest.raises(OSError):
        os.kill(pid, 0)  # the process is gone
    with pytest.raises(SessionLost):
        bl.ping()
    bl.close()


def test_crash_inside_blender_raises_session_lost(blender_bin):
    bl = BlenderSession(blender_bin, allow_exec=True).start()
    with pytest.raises(SessionLost, match="connection lost"):
        bl.exec_python("import os; os._exit(3)")
    assert not bl.alive
    bl.close()


def test_external_kill_raises_session_lost(blender_bin):
    bl = BlenderSession(blender_bin).start()
    os.kill(bl.info["pid"], signal.SIGKILL)
    time.sleep(0.5)
    with pytest.raises(SessionLost):
        bl.ping()
    bl.close()


def test_startup_failure_reports_exit_code(blender_bin):
    bl = BlenderSession(blender_bin, blend_file="/nonexistent/file.blend", startup_timeout=60)
    with pytest.raises(SessionLost):
        bl.start()
    assert not bl.alive
