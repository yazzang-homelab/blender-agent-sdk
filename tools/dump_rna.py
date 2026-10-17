"""Dump Blender's runtime RNA surface (operators + struct types) to JSON.

Run inside Blender:
    blender -b --factory-startup --python-exit-code 1 --python tools/dump_rna.py -- data/rna-5.2.2.json.gz

A path ending in .gz is written gzip-compressed (the raw dump is ~60 MB).
"""

import gzip
import json
import sys

import bpy


def _prop(p):
    entry = {
        "identifier": p.identifier,
        "type": p.type,
        "description": p.description,
    }
    if p.type in {"INT", "FLOAT", "BOOLEAN"}:
        length = getattr(p, "array_length", 0)
        if length:
            entry["array_length"] = length
    if p.type == "ENUM":
        entry["enum_items"] = [i.identifier for i in p.enum_items]
        entry["is_enum_flag"] = p.is_enum_flag
    if p.type in {"POINTER", "COLLECTION"} and p.fixed_type is not None:
        entry["fixed_type"] = p.fixed_type.identifier
    if p.is_readonly:
        entry["readonly"] = True
    if p.is_required:
        entry["required"] = True
    if p.type in {"INT", "FLOAT", "BOOLEAN", "STRING", "ENUM"} and not getattr(p, "array_length", 0):
        default = getattr(p, "default", None)
        if p.type == "ENUM":
            default = sorted(p.default_flag) if p.is_enum_flag else p.default
        if default is not None:
            entry["default"] = default
    return entry


def dump_operators():
    ops = {}
    for module_name in dir(bpy.ops):
        module = getattr(bpy.ops, module_name)
        for op_name in dir(module):
            idname = f"{module_name}.{op_name}"
            rna = getattr(module, op_name).get_rna_type()  # a failure here must abort the dump
            ops[idname] = {
                "bl_idname": rna.identifier,
                "name": rna.name,
                "description": rna.description,
                "properties": [_prop(p) for p in rna.properties if p.identifier != "rna_type"],
            }
    return ops


def dump_structs():
    structs = {}
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        rna = getattr(cls, "bl_rna", None)
        if rna is None or rna.identifier != name:
            continue
        structs[name] = {
            "base": rna.base.identifier if rna.base else None,
            "description": rna.description,
            "properties": [_prop(p) for p in rna.properties if p.identifier != "rna_type"],
            "functions": [f.identifier for f in rna.functions],
        }
    return structs


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else "rna.json"
    data = {
        "blender_version": bpy.app.version_string,
        "build_hash": bpy.app.build_hash.decode(),
        "operators": dump_operators(),
        "structs": dump_structs(),
    }
    opener = gzip.open if out.endswith(".gz") else open
    with opener(out, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    print(f"dump_rna: {len(data['operators'])} operators, {len(data['structs'])} structs -> {out}")


main()
