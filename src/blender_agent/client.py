"""Python client that owns a Blender process and talks to its bridge."""

import base64
import os
import shutil
import socket
import subprocess
import tempfile
import time
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


class RemoteError(BlenderAgentError):
    """A request raised inside Blender. The bridge is still alive."""

    def __init__(self, type_name, message, remote_traceback):
        super().__init__(f"{type_name}: {message}")
        self.type_name = type_name
        self.message = message
        self.remote_traceback = remote_traceback


def find_blender(explicit=None):
    """Resolve the Blender binary from an argument, $BLENDER, or PATH."""
    candidate = explicit or os.environ.get("BLENDER") or shutil.which("blender")
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
        self.log_path = log_path
        self.info = None
        self._proc = None
        self._sock = None
        self._tmpdir = None
        self._log = None
        self._next_id = 0

    # ------------------------------------------------------------- lifecycle

    def start(self):
        if self._proc is not None:
            raise BlenderAgentError("session already started")
        self._tmpdir = tempfile.mkdtemp(prefix="blender-agent-")  # mkdtemp creates it with mode 0700
        socket_path = os.path.join(self._tmpdir, "bridge.sock")
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(socket_path)
        listener.listen(1)
        listener.settimeout(0.5)

        cmd = [self.blender]
        if self.background:
            cmd.append("-b")
        if self.blend_file:
            cmd.append(os.fspath(self.blend_file))
        if self.factory_startup:
            cmd.append("--factory-startup")
        cmd += [*self.extra_args, "--python-exit-code", "1", "--python", str(BRIDGE_SCRIPT),
                "--", "--socket", socket_path]
        if self.allow_exec:
            cmd.append("--allow-exec")

        # Blender's stdout/stderr go straight to a file: nothing has to drain a pipe,
        # so a chatty render can never block the process.
        self.log_path = self.log_path or os.path.join(self._tmpdir, "blender.log")
        self._log = open(self.log_path, "wb")
        env = {**os.environ, **(self.env or {})}
        self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=self._log,
                                      stderr=subprocess.STDOUT, env=env)
        try:
            self._sock = self._accept(listener)
        except BaseException:
            self._kill()
            raise
        finally:
            listener.close()
        self._sock.settimeout(self.startup_timeout)
        try:
            self.info = wire.recv_frame(self._sock)
        except (OSError, wire.ProtocolError) as exc:
            self._kill()
            raise SessionLost(f"bridge did not say hello: {exc}\n{self.log_tail()}") from exc
        return self

    def _accept(self, listener):
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise SessionLost(f"Blender exited with code {self._proc.returncode} during startup\n{self.log_tail()}")
            try:
                conn, _ = listener.accept()
                return conn
            except socket.timeout:
                continue
        raise SessionLost(f"Blender did not connect within {self.startup_timeout}s\n{self.log_tail()}")

    def close(self):
        if self._proc is None:
            return
        if self._sock is not None and self._proc.poll() is None:
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
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None

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
            raise SessionLost("session is not running")
        self._next_id += 1
        request_id = self._next_id
        self._sock.settimeout(timeout or self.timeout)
        try:
            wire.send_frame(self._sock, {"id": request_id, "method": method, "params": params})
            response = wire.recv_frame(self._sock)
        except socket.timeout as exc:
            self._kill()
            raise SessionLost(f"{method} timed out after {timeout or self.timeout}s; Blender was killed") from exc
        except (OSError, wire.ProtocolError) as exc:
            code = self._proc.poll() if self._proc else None
            self._kill()
            raise SessionLost(f"connection lost during {method} (exit code {code}): {exc}") from exc
        if response.get("id") != request_id:
            self._kill()
            raise SessionLost(f"response id {response.get('id')} does not match request {request_id}")
        if not response.get("ok"):
            err = response.get("error") or {}
            raise RemoteError(err.get("type", "Error"), err.get("message", ""), err.get("traceback", ""))
        return response.get("result")

    def call(self, method, timeout=None, **params):
        """Invoke any bridge method by name."""
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
