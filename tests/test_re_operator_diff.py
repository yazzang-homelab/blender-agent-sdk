import gzip
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "re_operator_diff.py"


@pytest.fixture
def inputs(tmp_path):
    idnames = tmp_path / "idnames.txt"
    idnames.write_text("MESH_OT_primitive_cube_add\nGREASE_PENCIL_OT_delete\nRIGIDBODY_OT_world_export\n")
    rna = tmp_path / "rna.json.gz"
    with gzip.open(rna, "wt") as f:
        json.dump({"blender_version": "test", "build_hash": "0",
                   "operators": {"mesh.primitive_cube_add": {}, "grease_pencil.delete": {},
                                 "object.align": {}, "curve.draw": {}}}, f)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "ops.py").write_text('class A:\n    bl_idname = "object.align"\n')
    return idnames, rna, scripts, tmp_path


def _run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def test_classifies_operators(inputs):
    idnames, rna, scripts, tmp = inputs
    result = _run("--binary-idnames", idnames, "--rna", rna, "--scripts", scripts,
                  "--out", tmp / "out.md", "--json-out", tmp / "out.json")
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp / "out.json").read_text())
    assert report["both"] == 2  # GREASE_PENCIL_OT_ maps to grease_pencil.
    assert report["runtime_only_python"] == ["object.align"]
    assert report["runtime_only_unexplained"] == ["curve.draw"]
    assert report["binary_only"] == ["rigidbody.world_export"]


@pytest.mark.parametrize("bad", ["missing-dir", "a-file"])
def test_rejects_invalid_scripts_root_without_writing(inputs, bad):
    idnames, rna, _, tmp = inputs
    scripts = tmp / bad
    if bad == "a-file":
        scripts.write_text("")
    result = _run("--binary-idnames", idnames, "--rna", rna, "--scripts", scripts, "--out", tmp / "out.md")
    assert result.returncode != 0
    assert "is not a directory" in result.stderr
    assert not (tmp / "out.md").exists()
