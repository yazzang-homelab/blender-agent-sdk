"""Python client that owns a Blender process and talks to its bridge."""

import base64
import hmac
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

from . import protocol as wire

BRIDGE_SCRIPT = Path(__file__).with_name("bridge.py")


class BlenderAgentError(Exception):
    """Base class for blender-agent errors."""


class BlenderNotFound(BlenderAgentError):
    """No Blender executable was given or found."""


class SessionLost(BlenderAgentError):
    """The Blender process died, hung past its timeout, or closed the connection.

    The session is unusable afterwards; start a new one.
    """


class RequestTooLarge(BlenderAgentError):
    """A request exceeded the frame limit and was not sent. The session is unaffected."""


class RemoteError(BlenderAgentError):
    """A request raised inside Blender. The bridge is still alive."""

    def __init__(self, type_name, message, remote_traceback):
        super().__init__(f"{type_name}: {message}")
        self.type_name = type_name
        self.message = message
        self.remote_traceback = remote_traceback


def _installed_blenders():
    """Default install locations of the official macOS and Windows builds, newest first."""
    if sys.platform == "darwin":
        return [str(p) for p in (Path("/Applications/Blender.app/Contents/MacOS/Blender"),
                                 Path.home() / "Applications/Blender.app/Contents/MacOS/Blender") if p.is_file()]
    if os.name == "nt":
        root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Blender Foundation"
        found = [p for p in root.glob("Blender*/blender.exe") if p.is_file()]
        return [str(p) for p in sorted(found, key=lambda p: _version_key(p.parent.name), reverse=True)]
    return []


def _version_key(name):
    return tuple(int(n) for n in re.findall(r"\d+", name))


def find_blender(explicit=None):
    """Resolve the Blender binary from an argument, $BLENDER, PATH, or the default install location."""
    candidate = (explicit or os.environ.get("BLENDER") or shutil.which("blender")
                 or next(iter(_installed_blenders()), None))
    if not candidate:
        raise BlenderNotFound("set BLENDER=/path/to/blender, pass blender=..., or put blender on PATH")
    path = shutil.which(candidate) or candidate
    if not os.access(path, os.X_OK):
        raise BlenderNotFound(f"{candidate!r} is not an executable Blender binary")
    return path


class BlenderSession:
    """One Blender process plus a framed JSON-RPC connection to it.

    >>> with BlenderSession() as bl:
    ...     bl.call_operator("mesh.primitive_cube_add", {"size": 2})
    ...     png = bl.screenshot()
    """

    def __init__(self, blender=None, *, background=True, blend_file=None, allow_exec=False,
                 timeout=120.0, startup_timeout=60.0, factory_startup=True, extra_args=(), env=None,
                 log_path=None):
        self.blender = find_blender(blender)
        self.background = background
        self.blend_file = blend_file
        self.allow_exec = allow_exec
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.factory_startup = factory_startup
        self.extra_args = list(extra_args)
        self.env = env
        self._log_path_arg = log_path
        self.log_path = None
        self.info = None
        self._proc = None
        self._sock = None
        self._tmpdir = None
        self._log = None
        self._next_id = 0

    # ------------------------------------------------------------- lifecycle

    def start(self):
        if self._tmpdir is not None:
            raise BlenderAgentError("session already started")
        # Everything the session creates lives in this private directory (mkdtemp: 0700 on
        # POSIX, the user's own %TEMP% on Windows): the socket, Blender's log, and the
        # bridge's checkpoints and screenshots. _kill() removes it on every exit path,
        # including startup failures.
        self._tmpdir = tempfile.mkdtemp(prefix="blender-agent-")
        listener = None
        try:
            workdir = os.path.join(self._tmpdir, "work")
            os.mkdir(workdir)
            listener, address = self._listen()
            token = secrets.token_hex(32)

            cmd = [self.blender]
            if self.background:
                cmd.append("-b")
            if not self.allow_exec:
                cmd.append("--disable-autoexec")  # must precede the .blend to apply to it
            if self.blend_file:
                cmd.append(os.fspath(self.blend_file))
            if self.factory_startup:
                cmd.append("--factory-startup")
            cmd += [*self.extra_args, "--python-exit-code", "1", "--python", str(BRIDGE_SCRIPT),
                    "--", "--connect", address, "--workdir", workdir]
            if self.allow_exec:
                cmd.append("--allow-exec")

            # Blender's stdout/stderr go straight to a file: nothing has to drain a pipe,
            # so a chatty render can never block the process.
            self.log_path = self._log_path_arg or os.path.join(self._tmpdir, "blender.log")
            self._log = open(self.log_path, "wb")
            # The token travels in the environment, which other users cannot read (unlike argv).
            env = {**os.environ, **(self.env or {}), "BLENDER_AGENT_TOKEN": token}
            self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=self._log,
                                          stderr=subprocess.STDOUT, env=env)
            self._sock, self.info = self._accept(listener, token)
        except BaseException:
            self._kill()
            raise
        finally:
            if listener is not None:
                listener.close()
        return self

    def _lost(self, message):
        """Kill the session and build a SessionLost carrying the tail of Blender's log."""
        tail = self.log_tail()  # read before _kill() deletes the default log location
        self._kill()
        return SessionLost(f"{message}\n--- Blender log (tail) ---\n{tail}" if tail else message)

    def _listen(self):
        """Listening socket plus the address the bridge connects to."""
        if hasattr(socket, "AF_UNIX"):
            path = os.path.join(self._tmpdir, "bridge.sock")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(path)
            address = path
        else:  # Windows: CPython has no AF_UNIX there; loopback TCP, authenticated by the token
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            address = f"tcp:127.0.0.1:{listener.getsockname()[1]}"
        listener.listen(4)
        listener.settimeout(0.5)
        return listener, address

    def _accept(self, listener, token):
        """The connection that says hello with our token; any other peer is dropped."""
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise self._lost(f"Blender exited with code {self._proc.returncode} during startup")
            try:
                conn, _ = listener.accept()
            except socket.timeout:
                continue
            conn.settimeout(max(deadline - time.monotonic(), 0.5))
            try:
                hello = wire.recv_frame(conn)
            except (OSError, wire.ProtocolError):
                hello = None
            if isinstance(hello, dict) and hmac.compare_digest(str(hello.pop("token", "")), token):
                if conn.family != getattr(socket, "AF_UNIX", None):
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                return conn, hello
            conn.close()
        raise self._lost(f"Blender did not connect within {self.startup_timeout}s")

    def close(self):
        if self._tmpdir is None:
            return
        if self._sock is not None and self._proc is not None and self._proc.poll() is None:
            try:
                self._request("quit", {}, timeout=10)
                self._proc.wait(timeout=30)
            except (BlenderAgentError, subprocess.TimeoutExpired):
                pass
        self._kill()

    def _kill(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._tmpdir is not None:
            tmpdir, self._tmpdir = self._tmpdir, None
            try:
                shutil.rmtree(tmpdir)
            except OSError as exc:  # report, but never mask the error that brought us here
                warnings.warn(f"blender-agent could not remove {tmpdir}: {exc}", ResourceWarning, stacklevel=2)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    @property
    def alive(self):
        return self._proc is not None and self._proc.poll() is None and self._sock is not None

    @property
    def returncode(self):
        return None if self._proc is None else self._proc.poll()

    def log_tail(self, lines=40):
        if not self.log_path or not os.path.exists(self.log_path):
            return ""
        with open(self.log_path, "rb") as f:
            text = f.read().decode("utf-8", "replace")
        return "\n".join(text.splitlines()[-lines:])

    # ------------------------------------------------------------- transport

    def _request(self, method, params, timeout=None):
        if not self.alive:
            if self._tmpdir is not None:  # Blender died between requests
                raise self._lost(f"Blender is no longer running (exit code {self.returncode})")
            raise SessionLost("session is not running")
        self._next_id += 1
        request_id = self._next_id
        try:
            frame = wire.encode_frame({"id": request_id, "method": method, "params": params})
        except wire.FrameTooLarge as exc:
            raise RequestTooLarge(f"{method} request not sent: {exc}") from exc
        self._sock.settimeout(timeout or self.timeout)
        try:
            self._sock.sendall(frame)
            response = wire.recv_frame(self._sock)
        except socket.timeout as exc:
            raise self._lost(f"{method} timed out after {timeout or self.timeout}s; Blender was killed") from exc
        except (OSError, wire.ProtocolError) as exc:
            if self._proc is not None:
                try:  # give a crashing Blender a moment so its exit code is known
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            code = self._proc.poll() if self._proc else None
            raise self._lost(f"connection lost during {method} (exit code {code}): {exc}") from exc
        if not isinstance(response, dict) or response.get("id") != request_id:
            got = response.get("id") if isinstance(response, dict) else response
            raise self._lost(f"response id {got!r} does not match request {request_id}")
        if not response.get("ok"):
            err = response.get("error") or {}
            raise RemoteError(err.get("type", "Error"), err.get("message", ""), err.get("traceback", ""))
        return response.get("result")

    def request(self, method, params, timeout=None):
        """Invoke a bridge method with a params dict."""
        return self._request(method, params, timeout=timeout)

    def call(self, method, timeout=None, **params):
        """Invoke a bridge method with keyword params."""
        return self._request(method, params, timeout=timeout)

    # ------------------------------------------------------------- observe

    def ping(self):
        return self.call("ping")

    def scene_graph(self):
        return self.call("scene_graph")

    def object_info(self, name):
        return self.call("object_info", name=name)

    def screenshot(self, width=640, height=480, source="auto"):
        """Return ``(png_bytes, metadata)``."""
        meta = self.call("screenshot", width=width, height=height, source=source)
        return base64.b64decode(meta.pop("png_base64")), meta

    def get_property(self, collection, name, path):
        return self.call("get_property", collection=collection, name=name, path=path)["value"]

    # ------------------------------------------------------------- act

    def call_operator(self, idname, params=None, area_type=None, execution_context="EXEC_DEFAULT"):
        return self.call("call_operator", idname=idname, params=params or {}, area_type=area_type,
                         execution_context=execution_context)

    def set_property(self, collection, name, path, value):
        return self.call("set_property", collection=collection, name=name, path=path, value=value)["value"]

    def exec_python(self, code, timeout=None):
        return self.call("exec_python", timeout=timeout, code=code)

    def checkpoint(self, label=None):
        return self.call("checkpoint", label=label)["checkpoint"]

    def restore(self, checkpoint_id):
        return self.call("restore", checkpoint_id=checkpoint_id)

    def undo(self, steps=1):
        return self.call("undo", steps=steps)

    def save(self, filepath):
        return self.call("save", filepath=os.fspath(filepath))

    def open_file(self, filepath):
        return self.call("open_file", filepath=os.fspath(filepath))

    # ------------------------------------------------------------- discover

    def search_operators(self, query, limit=20):
        return self.call("search_operators", query=query, limit=limit)

    def describe_operator(self, idname):
        return self.call("describe_operator", idname=idname)
