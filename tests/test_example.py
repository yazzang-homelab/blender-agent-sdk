import importlib.util
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "agent_loop.py"


def test_scripted_agent_loop_end_to_end(blender_bin, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("agent_loop", EXAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main(["--policy", "scripted", "--blender", blender_bin, "--out", str(tmp_path)]) == 0
    shots = sorted(tmp_path.glob("step*.png"))
    assert shots and shots[-1].read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "result.blend").stat().st_size > 0
    assert "snowman" in capsys.readouterr().out
