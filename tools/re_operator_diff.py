"""Cross-check operators compiled into the Blender binary against the runtime RNA dump.

Inputs
  --binary-idnames  text file, one ``XXX_OT_name`` string per line, extracted from the
                    binary (docs/re/evidence/binary-operator-idnames.txt, produced from
                    REA ``search`` evidence).
  --rna             runtime dump written by tools/dump_rna.py (``.json`` or ``.json.gz``).
  --scripts         Blender's bundled ``<version>/scripts`` directory; Python operators are
                    defined there via ``bl_idname = "module.name"``.

Writes a Markdown report to --out.
"""

import argparse
import gzip
import json
import re
from collections import Counter
from pathlib import Path

# Module prefixes may contain underscores: GREASE_PENCIL_OT_delete -> grease_pencil.delete.
C_IDNAME = re.compile(r"^([A-Z][A-Z0-9_]*?)_OT_([a-z0-9_]+)$")
PY_BL_IDNAME = re.compile(r"""bl_idname\s*=\s*["']([a-z0-9_]+\.[a-z0-9_]+)["']""")


def to_python_name(c_idname):
    m = C_IDNAME.match(c_idname)
    return f"{m.group(1).lower()}.{m.group(2)}" if m else None


def load_rna(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def python_defined(scripts_dir):
    found = {}
    for py in Path(scripts_dir).rglob("*.py"):
        for name in PY_BL_IDNAME.findall(py.read_text(encoding="utf-8", errors="replace")):
            found.setdefault(name, str(py.relative_to(scripts_dir)))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binary-idnames", required=True, type=Path)
    ap.add_argument("--rna", required=True, type=Path)
    ap.add_argument("--scripts", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    if not args.scripts.is_dir():
        ap.error(f"--scripts {args.scripts} is not a directory")
    if not args.binary_idnames.is_file():
        ap.error(f"--binary-idnames {args.binary_idnames} is not a file")

    raw = [s.strip() for s in args.binary_idnames.read_text().splitlines() if s.strip()]
    binary = {to_python_name(s): s for s in raw if to_python_name(s)}
    rna = load_rna(args.rna)
    runtime = set(rna["operators"])
    py_ops = python_defined(args.scripts)

    both = sorted(runtime & binary.keys())
    runtime_only = sorted(runtime - binary.keys())
    runtime_only_py = [op for op in runtime_only if op in py_ops]
    runtime_only_unexplained = [op for op in runtime_only if op not in py_ops]
    binary_only = sorted(binary.keys() - runtime)

    by_module = Counter(op.split(".")[0] for op in binary_only)
    lines = [
        f"# Operator cross-check: binary vs runtime (Blender {rna['blender_version']}, build {rna['build_hash']})",
        "",
        "| set | count |",
        "|---|---:|",
        f"| `XXX_OT_*` idname strings found in the binary | {len(binary)} |",
        f"| operators registered at runtime (`bpy.ops`, factory startup, `-b`) | {len(runtime)} |",
        f"| in both | {len(both)} |",
        f"| runtime only, defined in bundled Python scripts | {len(runtime_only_py)} |",
        f"| runtime only, not found in bundled scripts | {len(runtime_only_unexplained)} |",
        f"| binary only (compiled in, not registered in this session) | {len(binary_only)} |",
        "",
        "## Runtime-only operators not explained by bundled scripts",
        "",
        *(f"- `{op}`" for op in runtime_only_unexplained),
        "" if runtime_only_unexplained else "_none_",
        "",
        "## Binary-only operators by module",
        "",
        "| module | count |",
        "|---|---:|",
        *(f"| `{m}` | {n} |" for m, n in by_module.most_common()),
        "",
        "## Binary-only operators",
        "",
        *(f"- `{op}` (`{binary[op]}`)" for op in binary_only),
        "",
    ]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    if args.json_out:
        args.json_out.write_text(json.dumps({
            "binary_count": len(binary), "runtime_count": len(runtime), "both": len(both),
            "runtime_only_python": runtime_only_py, "runtime_only_unexplained": runtime_only_unexplained,
            "binary_only": binary_only,
        }, indent=1), encoding="utf-8")
    print(f"binary={len(binary)} runtime={len(runtime)} both={len(both)} "
          f"runtime_only_py={len(runtime_only_py)} unexplained={len(runtime_only_unexplained)} "
          f"binary_only={len(binary_only)}")


if __name__ == "__main__":
    main()
