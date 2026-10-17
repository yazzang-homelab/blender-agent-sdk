# blender-agent-sdk

Drive Blender from AI agents with a plain Python SDK — **no MCP server, no addon to install**.

`BlenderSession` launches Blender (headless `-b` or with its GUI), injects a small bridge with
`--python`, and talks to it over a private Unix socket. On top of that sit computer-use style
tools — *observe* (scene graph, object state, screenshots), *discover* (search 2,498 operators) and
*act* (operators, RNA properties, checkpoints) — exported as ready-made OpenAI and Anthropic
function-calling schemas with a one-line `dispatch()`.

The design is grounded in a reverse-engineering pass over the Blender 5.2.2 binary itself with
[REA](https://github.com/morluto/rea) (Ghidra provider). See [`docs/re/`](docs/re/README.md) for the
evidence and its limits.

[한국어 설명은 아래에 있습니다.](#한국어)

```python
from blender_agent import BlenderSession

with BlenderSession() as bl:                      # blender -b, factory startup
    bl.call_operator("mesh.primitive_monkey_add", {"location": [0, 0, 1]})
    bl.call_operator("object.modifier_add", {"type": "SUBSURF"})
    bl.set_property("objects", "Suzanne", "modifiers['Subdivision'].levels", 2)
    print(bl.scene_graph()["objects"])
    png, meta = bl.screenshot(640, 480)          # PNG bytes; renders from the scene camera
```

## Install

Requires Python ≥ 3.10 and a Blender install. Tested on **Blender 5.2.2 LTS, Linux x64** only; other
versions and platforms are untested. Blender itself is not
bundled; point the SDK at it with `BLENDER=/path/to/blender`, `BlenderSession(blender=...)`, or `PATH`.

```bash
pip install git+https://github.com/yazzang-homelab/blender-agent-sdk
```

## Plug it into an agent

```python
import anthropic
from blender_agent import BlenderSession, anthropic_tools, dispatch
from blender_agent.tools import result_text

client = anthropic.Anthropic()
with BlenderSession() as bl:
    messages = [{"role": "user", "content": "Build a snowman and show me."}]
    while True:
        reply = client.messages.create(model="claude-sonnet-4-5", max_tokens=2048,
                                       tools=anthropic_tools(), messages=messages)
        messages.append({"role": "assistant", "content": reply.content})
        calls = [b for b in reply.content if b.type == "tool_use"]
        if not calls:
            break
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": result_text(dispatch(bl, c.name, c.input))}
            for c in calls]})
```

`openai_tools()` is the same list in OpenAI's `{"type": "function", ...}` shape, and `dispatch()` accepts
OpenAI's JSON-string arguments directly. [`examples/agent_loop.py`](examples/agent_loop.py) is a complete
loop for both APIs (screenshots are sent back as images) plus a scripted policy that needs no API key:

```bash
python examples/agent_loop.py --policy scripted --out agent-output
python examples/agent_loop.py --policy anthropic "build a low-poly tree"
```

## Tools

| tool | what it does |
|---|---|
| `scene_graph` | all objects with type, transform, dimensions, visibility, selection, collections; active object, camera, mode, engine |
| `object_info` | one object in depth: world bbox, modifiers, materials, mesh counts, light/camera data, custom props |
| `screenshot` | PNG of the scene (see modes below) |
| `search_operators` | keyword search over every registered `bpy.ops` operator |
| `describe_operator` | an operator's parameters, types and enum values |
| `call_operator` | run `bpy.ops.<idname>(**params)` inside a context override for an editor area |
| `get_property` / `set_property` | read/write any RNA path on a datablock, e.g. `modifiers["Bevel"].width` |
| `checkpoint` / `restore` | snapshot and roll back the whole file |
| `save` | write a `.blend` |
| `exec_python` | arbitrary Python inside Blender — **off unless** `BlenderSession(allow_exec=True)` *and* `openai_tools(include_exec=True)` |

Errors raised inside Blender come back as `RemoteError` (type, message, remote traceback) and the
session keeps running; `dispatch()` turns them into `{"ok": false, "error": ...}` so the model can
correct itself. A hung or crashed Blender raises `SessionLost` after the request timeout and the process
is killed.

## Background vs GUI sessions

| | `BlenderSession()` (`-b`) | `BlenderSession(background=False)` |
|---|---|---|
| execution | bridge blocks Blender's main thread and serves requests | reader thread + one `bpy.app.timers` callback on the main thread |
| `screenshot` | render from the scene camera (Workbench; a temporary camera framing visible objects when there is none) | offscreen draw of the 3D viewport (`GPUOffScreen.draw_view3d`), or `source="render"` |
| `undo` | refused — `-b` has no undo stack; use `checkpoint`/`restore` | `ed.undo`; operators are called with the undo flag so each one is a step |
| display | none needed | needs a display (`xvfb-run` works) |

Set `BLENDER_AGENT_RENDER_ENGINE=CYCLES` on machines without a GPU (CI does); Cycles then renders on the CPU.

## How it works

```
your agent ──dispatch()──► BlenderSession ──Unix socket (0700 dir), 4-byte length + JSON──► bridge.py in Blender
                              │  owns the process, timeouts,                                 │ bpy on the main thread
                              │  Blender log → file (never blocks)                           │
```

The process is launched as
`blender [-b] --factory-startup --python-exit-code 1 --python bridge.py -- --socket <path> [--allow-exec]`.
`exec_python` is gated by the bridge itself (from its launch arguments), not only by the client.

## Why not MCP?

MCP needs a separate server process, an addon installed into the user's Blender, and a host that
speaks MCP. Here the "server" is a child process you own: it can be headless, sandboxed per task, run
in CI, and its tools drop into any function-calling loop. Prior art for comparison:
[ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (MCP addon, GUI only) and
[ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent) (HTTP `exec` endpoint, no SDK).

## Reverse engineering

RE_SUMMARY

## Development

```bash
pip install -e ".[test]"
BLENDER=~/blender/blender pytest              # needs a real Blender; it fails, not skips, without one
xvfb-run -a pytest                            # also runs the GUI smoke test
UPDATE_GOLDEN=1 pytest tests/test_tools.py    # after an intentional tool-schema change
```

Regenerate the operator/RNA catalog: `blender -b --factory-startup --python tools/dump_rna.py -- data/rna-5.2.2.json.gz`.

## License

GPL-3.0-or-later. The bridge imports `bpy`, so the project follows Blender's license.
Blender binaries are never redistributed here.

---

## 한국어

AI 에이전트가 **MCP 없이** 순수 Python SDK로 Blender를 조작(computer-use)하게 해 주는 라이브러리입니다.

- `BlenderSession`이 Blender를 자식 프로세스로 띄우고(`-b` 헤드리스 또는 GUI), `--python`으로 브리지를 주입해
  전용 Unix 소켓(0700 디렉터리, 4바이트 길이 접두 JSON)으로 통신합니다. 애드온 설치가 필요 없습니다.
- 관찰(`scene_graph`, `object_info`, `screenshot`) · 탐색(`search_operators`, `describe_operator`) ·
  조작(`call_operator`, `set_property`, `checkpoint`/`restore`, `save`) 도구를 OpenAI/Anthropic
  function-calling 스키마로 제공하고 `dispatch()` 한 줄로 실행합니다.
- `exec_python`은 기본 비활성이며, 브리지가 실행 인자로 직접 차단합니다.
- Blender 내부 예외는 `RemoteError`(타입·메시지·원격 traceback)로 돌아오고 세션은 유지됩니다.
  멈추거나 죽으면 타임아웃 후 프로세스를 정리하고 `SessionLost`를 던집니다.
- 헤드리스(`-b`)에는 undo 스택이 없어 `checkpoint`/`restore`(.blend 스냅샷)를 쓰고, GUI 세션에서는
  `ed.undo`와 뷰포트 오프스크린 캡처를 씁니다.
- 설계 근거는 [REA](https://github.com/morluto/rea)(Ghidra 프로바이더)로 Blender 5.2.2 바이너리 자체를
  리버싱한 결과입니다. 증거와 한계는 [`docs/re/`](docs/re/README.md)에 있습니다.

테스트는 실제 Blender로 돕니다: `BLENDER=/path/to/blender pytest` (GUI까지: `xvfb-run -a pytest`).
라이선스는 GPL-3.0-or-later이며 Blender 바이너리는 포함하지 않습니다.
