# Reverse engineering Blender 5.2.2 with REA

This is the evidence behind the design of `blender-agent-sdk`. It covers the Blender binary itself, analyzed with
[REA](https://github.com/morluto/rea) 6.5.0 using its Ghidra 12.1.4 provider, together with a runtime dump of the RNA
type system. All conclusions below are labeled:

- **observed** – read directly from REA/Ghidra output or the runtime dump.
- **confirmed** – observed, and also matched against the Blender source at tag `v5.2.2`
  (commit `d13f752e3b9c`, which is the build hash printed by the binary).
- **inferred** – a reading of the evidence that the source did not check.

## Target

| | |
|---|---|
| file | `blender-5.2.2-linux-x64/blender` (official release tarball) |
| sha256 | `bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b` |
| size | 174,240,960 bytes, ELF64 x86-64, `EXEC_P`, entry `0x789920` |
| symbols | **stripped**: `objdump -t` reports "no symbols" ([evidence](evidence/objdump-symbols.json)); 1,696 defined dynamic symbols ([list](evidence/dynsym-defined.txt)) |
| toolchain | `.comment`: GCC 14.2.1 (Red Hat 14.2.1-7/-11) and clang 21.0.0git |

## Method

1. **Static inventory without a decompiler.** REA `inspect-artifact` ([evidence](evidence/inspect-artifact.json)) and
   `inspect-with-objdump` were used for file headers, section headers and symbols ([evidence](evidence/)).
   `inspect-binary-layout` (pwntools) refused the file. It has a 32 MiB input cap
   ([evidence](evidence/inspect-binary-layout-rejected.json)).
2. **Full Ghidra auto-analysis through REA.** `rea analyze --provider ghidra` ran on the whole binary
   ([overview](evidence/ghidra-analyze-overview.json)). It recovered **301,393 procedures** and **172,330 strings** in
   35 segments. Wall time was **70 min** (4,187 s) with a 14 GiB heap on a Ryzen AI 9 HX 370. Since there is no DWARF,
   every procedure carries a placeholder name (`FUN_xxxxxxxx`).
3. **Targeted queries against one live analysis.** Each `rea <command>` CLI call re-imports and re-analyzes the
   target, so [`tools/rea_session.py`](../../tools/rea_session.py) holds a single REA stdio session open and replays
   tool calls into it: `search_strings`, `xrefs`, `resolve_containing_procedure`, `procedure_pseudo_code` and
   `procedure_callers`. Once the analysis has finished, each query takes about 10 ms. Every request and its full
   Evidence record is stored under [`evidence/rea-session/`](evidence/rea-session/).
4. **Anchor-string identification.** The binary is stripped. To find a function, a string that only that function
   uses was taken from the v5.2.2 source, located with `search_strings`, and followed through `xrefs` to the
   containing procedure. That procedure was then decompiled and compared with the source.
5. **Runtime RNA dump.** [`tools/dump_rna.py`](../../tools/dump_rna.py) runs inside `blender -b --factory-startup`
   and writes every operator (with its properties) and every RNA struct to
   [`data/rna-5.2.2.json.gz`](../../data/rna-5.2.2.json.gz): 2,498 operators and 4,012 structs.
6. **Cross-check.** [`tools/re_operator_diff.py`](../../tools/re_operator_diff.py) compares the operator idnames
   compiled into the binary against the operators registered at runtime. The report is
   [operator-diff.md](operator-diff.md).

## Findings

### 1. Python is statically linked, and Blender's modules exist only inside its own interpreter (confirmed)

- A dedicated `.PyRuntime` section of 0x45310 bytes sits next to `.data`
  ([section headers](evidence/objdump-section_headers.json)). This is CPython's static runtime state.
- 1,681 of the 1,696 exported dynamic symbols are `Py*`/`_Py*`: the full embedding API (`Py_InitializeFromConfig`,
  `PyRun_*`, `PyEval_EvalCode`) plus 37 `PyInit_*` modules. Those modules include `mathutils*`, `aud` and
  `manta_main`. The bundle ships no `libpython*.so`, only `5.2/python/lib/libpython3.13.a` and 59 `lib-dynload`
  extension modules, which resolve their `Py*` imports against the executable.
- None of Blender's own modules is exported. `bmesh`, `gpu`, `blf`, `imbuf`, `idprop` and `mathutils` are registered
  through `bpy_internal_modules[]`, an `_inittab` defined in `source/blender/python/intern/bpy_interface.cc:320`.
  `bpy` is not in that table: `BPy_init_modules` (`source/blender/python/intern/bpy.cc:760`) creates the C module
  `_bpy` with `PyModule_New` and inserts it into `sys.modules` (:784-787). The pure-Python package
  `5.2/scripts/modules/bpy/__init__.py` then re-exports it (`from _bpy import ...`). Both mechanisms exist only in
  a running Blender, so these modules can be reached only by code in Blender's own interpreter.

Consequence for the SDK: an out-of-process client cannot `import bpy` or link against Blender. The bridge therefore has
to run inside Blender, and the cheapest entry point that needs no install is `--python <file>`.

### 2. The command line: `-b`, `--python`, `--python-exit-code` (confirmed)

`main_args_setup` was located by an xref from the string `--background`. REA located it at `FUN_0078d9d0`
([pseudocode](pseudocode/0x78d9d0_main_args_setup.c)). It registers each flag with its handler:

| flag | handler (binary) | source (`source/creator/creator_args.cc`) |
|---|---|---|
| `-b` / `--background` | `FUN_0078a7d0` ([pseudocode](pseudocode/0x78a7d0_arg_handle_background_mode_set.c)) | `arg_handle_background_mode_set` → `background_mode_set()` :1088 |
| `-P` / `--python` | `FUN_0078b500` ([pseudocode](pseudocode/0x78b500_arg_handle_python_file_run.c)) | `arg_handle_python_file_run` :2721 |
| `--python-exit-code` | `FUN_0078be50` ([pseudocode](pseudocode/0x78be50_arg_handle_python_exit_code_set.c)) | `arg_handle_python_exit_code_set` :2840 |

The `-b` handler sets a single global byte (`DAT_0aa2b9c1 = 1`, which is `G.background = true`) and forces the
audio device to `"None"`. That is the whole background mode. It does not tear down the window manager, which agrees
with the runtime observation that `bpy.context.window`/`screen` and a `VIEW_3D` area still exist under `-b`. What
background mode lacks is an event loop and an initialized GPU context (see finding 6), so:

- the bridge **owns the main thread** in `-b` (a blocking serve loop inside the `--python` script). `bpy.app.timers`
  never fire, because no event loop runs.
- `--python-exit-code 1` is passed so that a bridge crash at startup turns into a non-zero exit code. The client
  reports that code as `SessionLost`.

### 3. How a Python operator call reaches C (confirmed)

The strings `could not be found` and `cannot modify blend data in this state (drawing/rendering)` lead to
`FUN_02383cd0`, which is `bpy_op_fn_call_impl` ([pseudocode](pseudocode/0x2383cd0_bpy_op_fn_call_impl.c), source
`source/blender/python/intern/bpy_operator_function.cc:232`). The polling path, `FUN_02383900`, is
`bpy_op_fn_poll_impl` ([pseudocode](pseudocode/0x2383900_bpy_op_fn_poll_impl.c)). The decompiled order is:

1. Get the `bContext`. Fail with "Context is None" otherwise.
2. `WM_operatortype_find(idname)`.
3. Run a write check (fails while drawing or rendering).
4. Parse the context enum.
5. `WM_operator_poll_context`. On failure it raises `RuntimeError("Operator bpy.ops.X.poll() failed, context is incorrect")`.
6. Convert the keyword arguments to RNA properties (`"Converting py args to operator properties:"`).
7. Allocate a `wmOperatorReportList`.
8. **Release the GIL** (`PyEval_SaveThread`), call `WM_operator_call_py(..., is_undo)`, and take the GIL back.

SDK decisions that follow from this:

- `call_operator` runs `op.poll()` inside `context.temp_override(window, screen, area, region)` before calling. The
  agent gets "poll failed in the current context (mode=…)" instead of a bare RuntimeError.
- The `is_undo` argument is the only thing that makes a Python-invoked operator push an undo step. The bridge sets it
  in GUI sessions only. This was observed: `ed.undo` failed with "poll() failed, context is incorrect" until operators
  were called with the flag. The undo stack does not exist under `-b`, so `checkpoint`/`restore` (a `.blend` snapshot
  through `wm.save_as_mainfile(copy=True)` / `wm.open_mainfile`) is the mode-independent rollback.
- Releasing the GIL is safe only because every call happens on the main thread, which is the threading rule the bridge
  enforces.

### 4. Operator registration: a hash map filled by ~2,135 static call sites (confirmed)

The strings `Search for unknown operator '%s', '%s'` and `Operator '%s' has no name property` lead to
`WM_operatortype_find` (`FUN_016ac580`, [pseudocode](pseudocode/0x16ac580_WM_operatortype_find.c)) and
`wm_operatortype_append__end` (`FUN_016acda0`, [pseudocode](pseudocode/0x16acda0_wm_operatortype_append__end.c)).
The decompiler keeps Blender's `__FILE__:__LINE__` logging arguments, which pin the functions to
`source/blender/windowmanager/intern/wm_operator_type.cc:90` and `:126`. In the decompiled `find`, the Python-style
name is converted to `XXX_OT_name` and then looked up by probing an open-addressing hash table with `strlen`+`memcmp`.
That table is the `CustomIDVectorSet` in the source.

`procedure_callers` on `__end` gives its two wrappers, `WM_operatortype_append` (`FUN_016acf40`) and `…_append_ptr`
(`FUN_016acf70`). `xrefs` gives **2,135** and **4** call sites for them
([evidence](evidence/rea-session/44-x-append.json), [evidence](evidence/rea-session/45-x-append_ptr.json)). Together
with macro operators, this matches the C operator count found below.

### 5. Binary vs runtime operator inventory (observed, then confirmed)

REA `search_strings` with the regex `^[A-Z][A-Z0-9_]*_OT_[a-z0-9_]+$` returned 2,256 hits, or 2,247 unique idnames
([list](evidence/binary-operator-idnames.txt), [evidence](evidence/rea-session/02-search-ot.json)). An independent
raw-bytes regex over the file found the identical set. Comparing that set with the runtime dump
([full report](operator-diff.md)):

| | count |
|---|---:|
| idnames compiled into the binary | 2,247 |
| registered at runtime (`-b --factory-startup`) | 2,498 |
| in both | 2,237 |
| runtime only, defined in bundled Python (`5.2/scripts`, `bl_idname = …`) | 260 |
| runtime only, unexplained by scripts | 1 |
| binary only | 10 |

Every outlier was traced in the v5.2.2 source:

- `curve.draw` (runtime only): `CURVE_OT_draw` is in the binary, but only as the tail of `PAINTCURVE_OT_draw`
  (`…PAINTCURVE_OT_draw\0` at file offset `0x7ac830d`). The linker merged the two strings, so a whole-string search
  cannot see it. This is a limitation of string-based inventory, not a hidden operator.
- `view3d.vr_location_scouting_{browse_captures,add_camera_from_capture,add_marker_from_capture}`: C code looks these
  up by name (`view3d_vr_location_scouting.cc:259-279`), but the `viewport_vr_preview` add-on, which is disabled under
  factory startup, defines them in Python.
- `RIGIDBODY_OT_world_export`: compiled in, but its registration is commented out (`physics_ops.cc:89`).
- `OUTLINER_OT_lib_reload`, `SEQUENCER_OT_select_inverse`: the operator functions are compiled, but nothing calls
  `WM_operatortype_append` with them. They are dead code in 5.2.2.
- `PAINT_OT_brush_select`, `WM_OT_context_`, `ANIM_OT_channels`, `PAINT_OT_face_select`: these are not operators.
  They are keymap-versioning names and prefixes (`blenloader/intern/versioning_userdef.cc:501,571`,
  `windowmanager/intern/wm_keymap_utils.cc:364,406`).

Consequence: the runtime registry (`bpy.ops`, introspected through `get_rna_type()`) is the complete and authoritative
list of callable operators, and it includes the 260 Python operators the binary cannot show. `search_operators` and
`describe_operator` therefore query it live instead of shipping a static table. The dump in `data/` is the
reproducible snapshot for 5.2.2.

### 6. Screenshots: `GPUOffScreen.draw_view3d` needs an initialized GPU (confirmed)

The argument-parser format string `OOOOO&O&|$O&O&:draw_view3d` (`.rodata 0x7ece2ec`) points to a `_PyArg_Parser` in
`.data` (`0xa97a500`). Its only xref is in `FUN_0303bd80`, which is `pygpu_offscreen_draw_view3d`
([pseudocode](pseudocode/0x303bd80_pygpu_offscreen_draw_view3d.c), `source/blender/python/gpu/gpu_py_offscreen.cc:399`).
It raises "GPU offscreen was freed" and "Nested off-screen drawing not supported" (:466), and draws through the
viewport engine.

Correction to an earlier draft: `gpu` *can* be imported under `-b`. `BPyInit_gpu` has no background check
(`source/blender/python/gpu/gpu_py_api.cc:113-147`). What fails is drawing. Observed on 5.2.2: creating a
`GPUOffScreen` under `-b` raises "GPU functions for drawing requires the gpu module to be initialized. See
gpu.init". 5.2 adds `gpu.init()` ("Initializes the GPU module for background use", `gpu_py_api.cc:41-70`). It calls
`WM_init_gpu()` and raises `SystemError` when no GPU backend is available. On this machine (Radeon 890M),
`gpu.init()` followed by `draw_view3d` succeeded under `-b`. GitHub's hosted runners have no GPU. The SDK therefore
keeps background screenshots independent of the GPU:

- GUI session: `GPUOffScreen.draw_view3d` of the first `VIEW_3D` region. This works when the window is not
  composited, unlike `screen.screenshot_area`.
- Background session: `render.render(write_still=True)` from the scene camera. When there is none, a temporary
  camera framing all visible objects is used. The engine is Workbench, or `BLENDER_AGENT_RENDER_ENGINE` (Cycles CPU
  in CI).

## Limitations

- The binary is stripped. Procedure names in the pseudocode are Ghidra placeholders; the names in the table come from
  the anchor-string match against source, not from the binary. Any procedure not covered by an anchor string is
  unnamed.
- Only 10 procedures were decompiled, out of 301,393. Findings 2–4 and 6 rest on them; nothing else was audited.
- Ghidra logged pcode/varnode errors during auto-analysis (for example "Unable to resolve constructor",
  "VarnodeContext: out of address spaces"). Decompiled output can be locally wrong. All pseudocode used here was
  checked against source.
- String-based inventory misses tail-merged strings (see `curve.draw`) and anything whose name is built at run time.
- The runtime dump reflects `--factory-startup` with default add-ons. Enabling add-ons registers more operators.
- `inspect-binary-layout` (pwntools ELF layout, mitigations) could not run: the file is 5× its 32 MiB cap.
- One machine and one build: Linux x64, official 5.2.2 tarball. Other platforms were not examined.
- Time budget: the plan set a 3 h cap on REA work. Wall time was about 3.5 h (01:39–05:10) and went over the cap.
  The cause is that auto-analysis ran twice, about 70 min each. The first `rea analyze` produced only the overview,
  and each later `rea search` CLI call re-imported the binary. One persistent session
  (`tools/rea_session.py`) avoids that, and all targeted queries ran in it.

## Reproduce

```bash
npm i -g rea-agents            # 6.5.0; needs Node >= 22.19
export GHIDRA_INSTALL_DIR=/path/to/ghidra_12.1.4_PUBLIC GHIDRA_HEADLESS_MAXMEM=14G
rea inspect-with-objdump "$BLENDER" section_headers --format json
rea analyze "$BLENDER" --provider ghidra --format json           # ~70 min
mkdir q && echo '{"tool":"open_binary","arguments":{"path":"'"$BLENDER"'","provider_id":"ghidra"}}' > q/01.req.json
echo '{"tool":"search_strings","arguments":{"pattern":"^[A-Z][A-Z0-9_]*_OT_[a-z0-9_]+$","mode":"regex","case_sensitive":true}}' > q/02.req.json
python tools/rea_session.py serve q                                # writes q/*.res.json; touch q/stop to end
"$BLENDER" -b --factory-startup --python tools/dump_rna.py -- rna.json.gz
python tools/re_operator_diff.py --binary-idnames idnames.txt --rna rna.json.gz \
    --scripts "$(dirname "$BLENDER")/5.2/scripts" --out operator-diff.md
```

No Blender binaries, Ghidra projects or snapshots are committed. The evidence JSON records the sha256 of the analyzed
file.
