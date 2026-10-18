"""``blender-agent`` command line: MCP server, persistent sessions, terminal previews.

    blender-agent mcp [--gui] [--http 8765]          MCP server on stdio (Claude Code, Cursor, GJC, ...)
    blender-agent start [--name N] [--gui]           keep a Blender session running in the background
    blender-agent call [--name N] TOOL [JSON]        run one agent tool in that session
    blender-agent show [--name N] [--label TEXT]     render, add to the gallery, preview in the terminal
    blender-agent tools | status | list | stop       inspect and end sessions
    blender-agent view FILE.png                      draw an image in the terminal
    blender-agent watch [DIR]                        live terminal preview of the newest image
    blender-agent gallery DIR [--port 8765]          serve a gallery folder over HTTP

Sessions started with ``start`` outlive the command, so a person or a CLI agent can build a
scene over many turns. Every screenshot lands in a gallery folder (``index.html`` reloads
itself), can be served over HTTP, and is drawn in the terminal.
"""

import argparse
import base64
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from multiprocessing.connection import Client, Listener
from pathlib import Path

from . import termimg
from .client import BlenderAgentError
from .studio import Gallery, Studio
from .tools import TOOLS, result_text


def _home():
    if os.environ.get("BLENDER_AGENT_HOME"):
        return Path(os.environ["BLENDER_AGENT_HOME"])
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "blender-agent"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "blender-agent"


def _session_dir(name):
    path = _home() / "sessions" / name
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(_home(), 0o700)  # holds the session keys
    return path


def _add_session_options(p):
    p.add_argument("--blender", help="Blender executable (default: $BLENDER, PATH, standard install location)")
    p.add_argument("--gui", action="store_true", help="open Blender's window so you can watch the agent live")
    p.add_argument("--allow-exec", action="store_true",
                   help="allow exec_python and script operators (trusted agents only)")
    p.add_argument("--file", help=".blend file to start from")
    p.add_argument("--render-engine", choices=["BLENDER_WORKBENCH", "BLENDER_EEVEE", "CYCLES"],
                   help="engine for screenshots (default: $BLENDER_AGENT_RENDER_ENGINE or Workbench; "
                        "CYCLES on machines without a GPU). MCP hosts usually do not pass your environment on, "
                        "so set it here")
    p.add_argument("--out", help="gallery folder for screenshots")
    p.add_argument("--http", type=int, metavar="PORT",
                   help="also serve the gallery over HTTP on PORT (0 = any free port)")
    p.add_argument("--http-bind", default="127.0.0.1", metavar="ADDR",
                   help="address for --http (default 127.0.0.1; 0.0.0.0 to reach it from other devices)")


def _studio(args, default_out):
    gallery = Gallery(args.out or default_out, title=getattr(args, "name", None) or "blender-agent")
    env = {"BLENDER_AGENT_RENDER_ENGINE": args.render_engine} if args.render_engine else None
    studio = Studio(gallery, blender=args.blender, background=not args.gui, allow_exec=args.allow_exec,
                    blend_file=args.file, env=env)
    url = None
    if args.http is not None:
        try:
            server = gallery.serve(args.http, args.http_bind)
        except OSError as exc:  # e.g. a second session asked for the same port
            print(f"blender-agent: port {args.http} unavailable ({exc}); serving on a free port", file=sys.stderr)
            server = gallery.serve(0, args.http_bind)
        host, port = server.server_address[:2]
        url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/"
    return studio, url


# ------------------------------------------------------------------ mcp

def cmd_mcp(args):
    from .mcp_server import McpServer

    studio, url = _studio(args, Path.cwd() / "blender-agent-out")
    if url:
        print(f"blender-agent: gallery at {url} ({studio.gallery.dir})", file=sys.stderr)
    McpServer(studio, gallery_url=url).serve()


# ------------------------------------------------------------------ daemon

def cmd_daemon(args):
    """Internal: the background process behind ``start``."""
    if os.name != "nt":  # stop/kill -> close Blender and remove the state, as for `stop`
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        signal.signal(signal.SIGHUP, lambda *_: sys.exit(0))
    state_dir = _session_dir(args.name)
    studio, url = _studio(args, Path(args.out) if args.out else state_dir / "gallery")
    authkey = secrets.token_bytes(32)
    if os.name == "nt":
        listener = Listener(rf"\\.\pipe\blender-agent-{secrets.token_hex(8)}", "AF_PIPE", authkey=authkey)
    else:  # a short private path: Unix socket paths are limited to ~104 bytes on macOS
        sock_dir = tempfile.mkdtemp(prefix="blender-agent-d-")
        listener = Listener(os.path.join(sock_dir, "s"), "AF_UNIX", authkey=authkey)
    try:
        try:
            studio.session  # start Blender now so `start` can report failures
        except BaseException:
            (state_dir / "failed").write_text("startup failed\n")
            raise
        state = {"pid": os.getpid(), "address": listener.address, "family": "AF_PIPE" if os.name == "nt" else "AF_UNIX",
                 "authkey": authkey.hex(), "gallery": str(studio.gallery.dir), "url": url,
                 "gui": args.gui, "allow_exec": args.allow_exec, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
        state_file = state_dir / "state.json"
        tmp = state_dir / "state.json.tmp"
        tmp.write_text(json.dumps(state))
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, state_file)
        running = True
        while running:
            try:
                conn = listener.accept()
            except Exception as exc:  # a client with the wrong key, or one that hung up early
                print(f"blender-agent daemon: rejected connection: {exc}", file=sys.stderr, flush=True)
                continue
            with conn:
                try:
                    request = json.loads(conn.recv_bytes())
                except (EOFError, OSError, ValueError):
                    continue
                reply, running = _daemon_reply(studio, url, request)
                conn.send_bytes(json.dumps(reply, ensure_ascii=False).encode("utf-8"))
    finally:
        listener.close()
        studio.close()
        (state_dir / "state.json").unlink(missing_ok=True)
        if os.name != "nt":
            shutil.rmtree(sock_dir, ignore_errors=True)


def _daemon_reply(studio, url, request):
    op = request.get("op")
    if op == "stop":
        return {"ok": True}, False
    if op == "info":
        return {"ok": True, "gallery": str(studio.gallery.dir), "url": url, "shots": len(studio.gallery.entries),
                "restarts": studio.restarts}, True
    if op == "reset":
        return {"ok": True, "result": studio.reset()}, True
    if op == "call":
        outcome = studio.run(request["tool"], request.get("args") or {}, label=request.get("label", ""))
        png = outcome.pop("image_png", None)
        reply = json.loads(result_text({**outcome, "image_png": None}))
        if outcome.get("shot"):
            reply["shot"] = outcome["shot"]
        if png and request.get("want_image"):
            reply["image_png"] = base64.b64encode(png).decode("ascii")
        return reply, True
    return {"ok": False, "error": f"unknown op {op!r}"}, True


def _state(name):
    path = _home() / "sessions" / name / "state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _send(name, request, timeout=None):
    state = _state(name)
    if state is None:
        raise SystemExit(f"no running session {name!r}; start one with: blender-agent start --name {name}")
    try:
        with Client(state["address"], state["family"], authkey=bytes.fromhex(state["authkey"])) as conn:
            conn.send_bytes(json.dumps(request).encode("utf-8"))
            return json.loads(conn.recv_bytes())
    except (OSError, EOFError) as exc:
        (_home() / "sessions" / name / "state.json").unlink(missing_ok=True)
        raise SystemExit(f"session {name!r} is not responding ({exc}); start it again") from exc


def _alive(name):
    """True when a session answers; forgets the state of one that does not."""
    if _state(name) is None:
        return False
    try:
        _send(name, {"op": "info"})
        return True
    except SystemExit:
        return False


_FORWARDED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "BLENDER", "BLENDER_AGENT_HOME", "BLENDER_AGENT_RENDER_ENGINE",
                  "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "PYTHONPATH")


def _outside_caller_cgroup(argv, name, log_path):
    """On systemd Linux, run the daemon as a transient user service.

    Agent harnesses and terminal multiplexers often kill every process the command
    started when it returns (cgroup or process-tree cleanup), which a new session alone
    does not escape. Returns None where systemd's user manager is not available or
    BLENDER_AGENT_DETACH=plain asks for a plain detached process.
    """
    if not sys.platform.startswith("linux") or os.environ.get("BLENDER_AGENT_DETACH") == "plain":
        return None
    systemd_run = shutil.which("systemd-run")
    if not systemd_run or subprocess.run([systemd_run, "--user", "--quiet", "--collect", "--wait", "true"],
                                         capture_output=True, timeout=10).returncode != 0:
        return None
    env = [f"--setenv={k}={os.environ[k]}" for k in _FORWARDED_ENV if k in os.environ]
    return [systemd_run, "--user", "--quiet", "--collect", f"--unit=blender-agent-{name}-{secrets.token_hex(3)}",
            f"--working-directory={os.getcwd()}", f"--property=StandardOutput=append:{log_path}",
            "--property=StandardError=inherit", *env, "--", *argv]


def cmd_start(args):
    if _alive(args.name):
        raise SystemExit(f"session {args.name!r} is already running; stop it first")
    state_dir = _session_dir(args.name)
    failed = state_dir / "failed"  # written by the daemon when it cannot start
    failed.unlink(missing_ok=True)
    log_path = state_dir / "daemon.log"
    log_path.write_bytes(b"")
    argv = [sys.executable, "-m", "blender_agent", "_daemon", "--name", args.name]
    for flag in ("blender", "file", "out", "http", "render_engine"):
        if getattr(args, flag) is not None:
            argv += [f"--{flag.replace('_', '-')}", str(getattr(args, flag))]
    argv += ["--http-bind", args.http_bind] + ["--gui"] * args.gui + ["--allow-exec"] * args.allow_exec
    service = _outside_caller_cgroup(argv, args.name, log_path)
    kwargs = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} \
        if os.name == "nt" else {"start_new_session": True}
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(service or argv, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                **kwargs)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        state = _state(args.name)
        if state:
            print(f"session {args.name!r} running (pid {state['pid']})")
            print(f"gallery: {state['gallery']}")
            if state["url"]:
                print(f"web:     {state['url']}")
            return
        # systemd-run exits 0 once the service is queued; the daemon reports its own failure.
        exited = proc.poll() is not None and (proc.returncode != 0 or not service)
        if exited or failed.exists():
            tail = log_path.read_text(errors="replace")[-3000:]
            raise SystemExit(f"session {args.name!r} failed to start:\n{tail}")
        time.sleep(0.2)
    if proc.poll() is None:
        proc.kill()
    raise SystemExit(f"session {args.name!r} did not start within {args.timeout}s; see {log_path}")


def _print_outcome(reply, preview, columns):
    image = reply.pop("image_png", None)
    print(json.dumps(reply, ensure_ascii=False, indent=1))
    if image and preview:
        sys.stdout.write(termimg.render(base64.b64decode(image), columns))
    return 0 if reply.get("ok") else 1


def _preview_default(args):
    return sys.stdout.isatty() if args.preview is None else args.preview


def cmd_call(args):
    try:
        arguments = json.loads(args.json) if args.json else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"arguments are not valid JSON: {exc}") from exc
    preview = _preview_default(args)
    reply = _send(args.name, {"op": "call", "tool": args.tool, "args": arguments, "want_image": preview})
    return _print_outcome(reply, preview, args.columns)


def cmd_show(args):
    preview = _preview_default(args)
    shot = {k: v for k, v in (("width", args.width), ("height", args.height), ("source", args.source)) if v}
    reply = _send(args.name, {"op": "call", "tool": "screenshot", "args": shot, "label": args.label,
                              "want_image": preview})
    return _print_outcome(reply, preview, args.columns)


def cmd_status(args):
    print(json.dumps(_send(args.name, {"op": "info"}), ensure_ascii=False, indent=1))


def cmd_list(args):
    root = _home() / "sessions"
    names = sorted(p.name for p in root.iterdir() if (p / "state.json").exists()) if root.exists() else []
    for name in names:
        state = _state(name)
        print(f"{name}\tpid {state['pid']}\t{'gui' if state['gui'] else 'background'}\t{state['gallery']}")


def cmd_stop(args):
    names = [p.name for p in (_home() / "sessions").iterdir() if (p / "state.json").exists()] \
        if args.all and (_home() / "sessions").exists() else [args.name]
    for name in names:
        _send(name, {"op": "stop"})
        deadline = time.monotonic() + 30
        while _state(name) and time.monotonic() < deadline:
            time.sleep(0.1)
        print(f"stopped {name}")


def cmd_reset(args):
    print(json.dumps(_send(args.name, {"op": "reset"}), indent=1))


def cmd_tools(args):
    for tool in TOOLS:
        params = ", ".join(f"{k}{'' if k in tool['parameters']['required'] else '?'}"
                           for k in tool["parameters"]["properties"])
        print(f"{tool['name']}({params})\n    {tool['description']}")


def cmd_view(args):
    sys.stdout.write(termimg.render(Path(args.file).read_bytes(), args.columns))


def cmd_watch(args):
    """Redraw the newest gallery image whenever one arrives: a live preview pane for tmux."""
    directory = Path(args.dir) if args.dir else Path(_state_or_exit(args.name)["gallery"])
    history, seen = directory / "history.jsonl", None
    try:
        while True:
            lines = history.read_text(encoding="utf-8").splitlines() if history.exists() else []
            if lines and lines[-1] != seen:
                seen = lines[-1]
                entry = json.loads(seen)
                columns = args.columns or max(20, shutil.get_terminal_size((80, 24)).columns - 2)
                sys.stdout.write("\x1b[H\x1b[2J" + termimg.render((directory / entry["file"]).read_bytes(), columns))
                sys.stdout.write(f"#{entry['n']} {entry['label']}  {entry['time']}  ({directory})\n")
                sys.stdout.flush()
            if args.once:
                return 0 if seen else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def _state_or_exit(name):
    state = _state(name)
    if state is None:
        raise SystemExit(f"no running session {name!r}; pass a gallery folder instead")
    return state


def cmd_gallery(args):
    gallery = Gallery(args.dir)
    server = gallery.serve(args.port, args.bind)
    host, port = server.server_address[:2]
    print(f"serving {gallery.dir} at http://{host}:{port}/ (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


# ------------------------------------------------------------------ parser

def build_parser():
    parser = argparse.ArgumentParser(prog="blender-agent", description="Drive Blender from agents and terminals: "
                                     "MCP server, persistent sessions, terminal previews.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    columns = max(20, min(120, shutil.get_terminal_size((80, 24)).columns - 2))

    p = sub.add_parser("mcp", help="MCP server on stdio")
    _add_session_options(p)
    p.set_defaults(func=cmd_mcp)

    for name, func, help_text in (("start", cmd_start, "start a background session"), ("_daemon", cmd_daemon, None)):
        p = sub.add_parser(name, help=help_text) if help_text else sub.add_parser(name)
        p.add_argument("--name", default="default")
        p.add_argument("--timeout", type=float, default=120.0, help=argparse.SUPPRESS)
        _add_session_options(p)
        p.set_defaults(func=func)

    for name, func, help_text in (("call", cmd_call, "run one tool"), ("show", cmd_show, "render and preview")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--name", default="default")
        p.add_argument("--preview", action=argparse.BooleanOptionalAction, default=None,
                       help="draw returned images in the terminal (default: when stdout is a terminal)")
        p.add_argument("--columns", type=int, default=columns)
        p.set_defaults(func=func)
        if name == "call":
            p.add_argument("tool", choices=[t["name"] for t in TOOLS])
            p.add_argument("json", nargs="?", help="arguments as a JSON object")
        else:
            p.add_argument("--label", default="")
            p.add_argument("--width", type=int)
            p.add_argument("--height", type=int)
            p.add_argument("--source", choices=["auto", "render", "viewport"])

    for name, func, help_text in (("status", cmd_status, "session info"), ("stop", cmd_stop, "stop a session"),
                                  ("reset", cmd_reset, "discard the scene, restart Blender")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--name", default="default")
        if name == "stop":
            p.add_argument("--all", action="store_true")
        p.set_defaults(func=func)

    sub.add_parser("list", help="running sessions").set_defaults(func=cmd_list)
    sub.add_parser("tools", help="list agent tools").set_defaults(func=cmd_tools)

    p = sub.add_parser("view", help="draw a PNG in the terminal")
    p.add_argument("file")
    p.add_argument("--columns", type=int, default=columns)
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("watch", help="live terminal preview of a gallery (run it in a tmux pane)")
    p.add_argument("dir", nargs="?", help="gallery folder (default: the --name session's)")
    p.add_argument("--name", default="default")
    p.add_argument("--columns", type=int, default=0)
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--once", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("gallery", help="serve a gallery folder over HTTP")
    p.add_argument("dir")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--bind", default="127.0.0.1")
    p.set_defaults(func=cmd_gallery)
    return parser


def main(argv=None):
    # UTF-8 everywhere (previews, labels, MCP frames), also on Windows consoles and pipes.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", **({} if stream is sys.stdin else {"newline": "\n"}))
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except BlenderAgentError as exc:
        print(f"blender-agent: {exc}", file=sys.stderr)
        return 1
