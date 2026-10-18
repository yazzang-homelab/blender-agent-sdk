"""The ``blender-agent`` command line: background sessions, previews, gallery."""

import json
import subprocess
import sys
from multiprocessing.connection import Client

import pytest


@pytest.fixture
def cli(tmp_path, blender_bin, monkeypatch):
    env_home = tmp_path / "home"

    def run(*args, check=True):
        proc = subprocess.run([sys.executable, "-m", "blender_agent", *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=180,
                              env={**__import__("os").environ, "BLENDER_AGENT_HOME": str(env_home),
                                   "BLENDER": blender_bin})
        if check and proc.returncode != 0:
            raise AssertionError(f"{args} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc

    run.home = env_home
    yield run
    run("stop", "--all", check=False)


def _json_head(text):
    """The JSON object a command printed before any terminal preview."""
    return json.JSONDecoder().raw_decode(text)[0]


def test_session_persists_across_commands(cli, tmp_path):
    out = tmp_path / "gallery"
    started = cli("start", "--name", "demo", "--out", str(out))
    assert "running" in started.stdout and str(out) in started.stdout
    assert "demo" in cli("list").stdout

    cli("call", "--name", "demo", "call_operator", '{"idname": "mesh.primitive_monkey_add"}')
    graph = _json_head(cli("call", "--name", "demo", "scene_graph").stdout)
    assert "Suzanne" in {o["name"] for o in graph["result"]["objects"]}

    shown = cli("show", "--name", "demo", "--label", "monkey", "--width", "64", "--height", "48",
                "--preview", "--columns", "20")
    reply = _json_head(shown.stdout)
    assert reply["shot"]["label"] == "monkey" and (out / "shots" / "0001.png").exists()
    assert "▀" in shown.stdout  # drawn in the terminal

    watched = cli("watch", str(out), "--once", "--columns", "20")
    assert "#1 monkey" in watched.stdout

    refused = cli("call", "--name", "demo", "call_operator", '{"idname": "script.python_file_run"}', check=False)
    assert refused.returncode == 1 and "refused without allow_exec" in refused.stdout

    cli("stop", "--name", "demo")
    gone = cli("call", "--name", "demo", "scene_graph", check=False)
    assert gone.returncode != 0 and "no running session" in gone.stderr


def test_daemon_rejects_clients_without_the_key(cli):
    cli("start", "--name", "keyed")
    state = json.loads((cli.home / "sessions" / "keyed" / "state.json").read_text())
    with pytest.raises(Exception):
        with Client(state["address"], state["family"], authkey=b"wrong" * 8) as conn:
            conn.send_bytes(b'{"op": "stop"}')
    assert _json_head(cli("status", "--name", "keyed").stdout)["ok"] is True  # still serving


def test_start_reports_a_failing_blender(cli, tmp_path):
    broken = cli("start", "--name", "bad", "--file", str(tmp_path / "missing.blend"), check=False)
    assert broken.returncode != 0 and "failed to start" in broken.stderr


def test_view_draws_a_png(cli, tmp_path, session):
    png, _ = session.screenshot(40, 30)
    (tmp_path / "s.png").write_bytes(png)
    out = cli("view", str(tmp_path / "s.png"), "--columns", "10").stdout
    assert out.count("\n") == 4 and "▀" in out  # 30 px tall at 10 columns of 40 px -> 4 lines


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_terminated_daemon_closes_blender_and_forgets_the_session(cli):
    import os
    import signal
    import time

    cli("start", "--name", "term")
    state = json.loads((cli.home / "sessions" / "term" / "state.json").read_text())
    os.kill(state["pid"], signal.SIGTERM)
    deadline = time.monotonic() + 30
    while (cli.home / "sessions" / "term" / "state.json").exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not (cli.home / "sessions" / "term" / "state.json").exists()
    assert "term" not in cli("list").stdout
