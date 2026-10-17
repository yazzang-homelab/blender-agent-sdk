"""Minimal observe -> act agent loop over blender-agent.

    python examples/agent_loop.py --policy scripted          # no API key needed
    python examples/agent_loop.py --policy anthropic "build a snowman"
    python examples/agent_loop.py --policy openai "build a snowman"

The LLM sees the same tool list either way; only the request/response wiring differs.
"""

import argparse
import json
import sys
from pathlib import Path

from blender_agent import BlenderSession, anthropic_tools, dispatch, openai_tools
from blender_agent.tools import image_base64, result_text

SYSTEM = ("You control Blender through tools. Inspect with scene_graph/object_info/screenshot, find operators "
          "with search_operators/describe_operator, act with call_operator/set_property, and take a checkpoint "
          "before destructive steps. Finish with a screenshot and a one-line summary.")


def scripted(session, task, out_dir):
    """Deterministic policy: a fixed tool plan that exercises observe, discover and act."""
    plan = [
        ("checkpoint", {"label": "start"}),
        ("search_operators", {"query": "add uv sphere", "limit": 3}),
        ("call_operator", {"idname": "mesh.primitive_uv_sphere_add", "params": {"radius": 1.0, "location": [0, 0, 1]}}),
        ("call_operator", {"idname": "mesh.primitive_uv_sphere_add", "params": {"radius": 0.7, "location": [0, 0, 2.5]}}),
        ("call_operator", {"idname": "mesh.primitive_uv_sphere_add", "params": {"radius": 0.45, "location": [0, 0, 3.6]}}),
        ("set_property", {"collection": "objects", "name": "Cube", "path": "scale", "value": [3, 3, 0.05]}),
        ("set_property", {"collection": "objects", "name": "Cube", "path": "location", "value": [0, 0, -0.05]}),
        ("scene_graph", {}),
        ("screenshot", {"width": 640, "height": 480}),
    ]
    for step, (name, args) in enumerate(plan, 1):
        outcome = dispatch(session, name, args)
        print(f"[{step}] {name} -> {result_text(outcome)[:160]}")
        if not outcome["ok"]:
            raise SystemExit(f"step {step} failed: {outcome['error']}")
        if outcome["image_png"]:
            path = out_dir / f"step{step:02d}.png"
            path.write_bytes(outcome["image_png"])
            print(f"     saved {path}")
    return "built a three-ball snowman on a ground slab"


def anthropic_loop(session, task, out_dir, model="claude-sonnet-4-5", max_turns=30):
    import anthropic

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": task}]
    for _ in range(max_turns):
        reply = client.messages.create(model=model, max_tokens=2048, system=SYSTEM,
                                       tools=anthropic_tools(), messages=messages)
        messages.append({"role": "assistant", "content": reply.content})
        calls = [b for b in reply.content if b.type == "tool_use"]
        if not calls:
            return "".join(b.text for b in reply.content if b.type == "text")
        results = []
        for call in calls:
            outcome = dispatch(session, call.name, call.input)
            content = [{"type": "text", "text": result_text(outcome)}]
            if outcome["image_png"]:
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                             "data": image_base64(outcome)}})
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": content,
                            "is_error": not outcome["ok"]})
        messages.append({"role": "user", "content": results})
    return None  # turn limit reached


def openai_loop(session, task, out_dir, model="gpt-5", max_turns=30):
    from openai import OpenAI

    client = OpenAI()
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for _ in range(max_turns):
        reply = client.chat.completions.create(model=model, messages=messages, tools=openai_tools())
        msg = reply.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            return msg.content
        images = []
        for call in msg.tool_calls:
            outcome = dispatch(session, call.function.name, call.function.arguments)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result_text(outcome)})
            if outcome["image_png"]:
                images.append(image_base64(outcome))
        if images:  # tool messages cannot carry images, so attach them as a user turn
            messages.append({"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}} for data in images]})
    return None  # turn limit reached


POLICIES = {"scripted": scripted, "anthropic": anthropic_loop, "openai": openai_loop}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task", nargs="?", default="Build a simple snowman and show it to me.")
    parser.add_argument("--policy", choices=sorted(POLICIES), default="scripted")
    parser.add_argument("--blender", help="Blender executable (default: $BLENDER or PATH)")
    parser.add_argument("--out", type=Path, default=Path("agent-output"))
    parser.add_argument("--gui", action="store_true", help="run Blender with its window instead of -b")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    with BlenderSession(args.blender, background=not args.gui) as session:
        summary = POLICIES[args.policy](session, args.task, args.out)
        session.save(args.out / "result.blend")
    if summary is None:
        print(json.dumps({"error": "turn limit reached", "output": str(args.out)}, ensure_ascii=False))
        return 2
    print(json.dumps({"summary": summary, "output": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
