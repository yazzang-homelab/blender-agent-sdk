"""A long-lived Blender session for conversational use, plus a gallery of what it showed.

:class:`Studio` is what the MCP server (``blender-agent mcp``) and the session daemon
(``blender-agent start``) share: it starts Blender on the first tool call, keeps it
across calls, restarts it after a crash, and records every screenshot in a
:class:`Gallery` so a person can follow along while an agent works.
"""

import functools
import html
import json
import os
import shutil
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .client import BlenderSession, SessionLost
from .tools import dispatch

__all__ = ["Gallery", "Studio"]

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="3">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>blender-agent: {title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #1e1f22; color: #ddd; }}
img {{ max-width: 100%; border-radius: 6px; }}
.latest img {{ max-height: 75vh; }}
.strip {{ display: flex; flex-wrap: wrap; gap: .75rem; margin-top: 1rem; }}
.strip figure {{ margin: 0; width: 200px; }}
figcaption {{ font-size: .8rem; color: #aaa; }}
a {{ color: #8ab4f8; }}
</style></head><body>
<h1>{title}</h1>
{latest}
<div class="strip">{strip}</div>
<p><a href="history.jsonl">history.jsonl</a> · reloads every 3 s</p>
</body></html>
"""


class Gallery:
    """Screenshots in ``out_dir/shots``, ``latest.png``, ``history.jsonl`` and an ``index.html``
    that reloads itself, so the newest image is always one refresh away."""

    def __init__(self, out_dir, title="blender-agent"):
        self.dir = Path(out_dir).resolve()
        self.title = title
        (self.dir / "shots").mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._entries = []
        history = self.dir / "history.jsonl"
        if history.exists():
            self._entries = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line]
        self._write_index()

    @property
    def entries(self):
        return list(self._entries)

    def add(self, png, label="", meta=None):
        """Store one screenshot; returns its history entry (with ``path``)."""
        with self._lock:
            number = (self._entries[-1]["n"] + 1) if self._entries else 1
            name = f"shots/{number:04d}.png"
            (self.dir / name).write_bytes(png)
            shutil.copyfile(self.dir / name, self.dir / "latest.png")
            entry = {"n": number, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "label": label,
                     "file": name, "meta": meta or {}}
            self._entries.append(entry)
            with open(self.dir / "history.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._write_index()
        return {**entry, "path": str(self.dir / name)}

    def _write_index(self):
        latest = ""
        if self._entries:
            e = self._entries[-1]
            latest = (f'<figure class="latest"><img src="{e["file"]}" alt="latest">'
                      f'<figcaption>#{e["n"]} {html.escape(e["label"])} · {e["time"]}</figcaption></figure>')
        strip = "".join(
            f'<figure><a href="{e["file"]}"><img src="{e["file"]}" alt="#{e["n"]}"></a>'
            f'<figcaption>#{e["n"]} {html.escape(e["label"])}</figcaption></figure>'
            for e in reversed(self._entries[:-1]))
        page = _PAGE.format(title=html.escape(self.title), latest=latest or "<p>No screenshots yet.</p>", strip=strip)
        tmp = self.dir / "index.html.tmp"
        tmp.write_text(page, encoding="utf-8")
        os.replace(tmp, self.dir / "index.html")

    def serve(self, port=0, bind="127.0.0.1"):
        """Serve the gallery over HTTP from a daemon thread; returns the server (``.server_address``)."""

        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer((bind, port), functools.partial(Quiet, directory=str(self.dir)))
        threading.Thread(target=server.serve_forever, name="blender-agent-gallery", daemon=True).start()
        return server


class Studio:
    """One Blender session kept alive across tool calls, restarted after it is lost."""

    def __init__(self, gallery, *, blender=None, background=True, allow_exec=False, blend_file=None, env=None,
                 session_factory=BlenderSession):
        self.gallery = gallery
        self.options = {"blender": blender, "background": background, "allow_exec": allow_exec,
                        "blend_file": blend_file, "env": env}
        self._factory = session_factory
        self._session = None
        self.restarts = 0

    @property
    def session(self):
        if self._session is None or not self._session.alive:
            if self._session is not None:
                self._session.close()
                self.restarts += 1
            self._session = self._factory(**self.options).start()
        return self._session

    def run(self, tool, arguments, label=""):
        """Run one agent tool. Screenshots go to the gallery; the outcome gains ``shot``."""
        try:
            outcome = dispatch(self.session, tool, arguments)
        except SessionLost as exc:
            # The next call starts a fresh Blender; this one reports what was lost.
            return {"ok": False, "image_png": None,
                    "error": f"Blender session lost and will restart on the next call "
                             f"(unsaved changes are gone): {exc}"}
        if outcome["ok"] and outcome.get("image_png"):
            entry = self.gallery.add(outcome["image_png"], label or tool, outcome.get("result"))
            outcome["shot"] = entry
        return outcome

    def reset(self):
        """Discard the scene: start a new Blender session."""
        if self._session is not None:
            self._session.close()
            self._session = None
        return self.session.ping()

    def close(self):
        if self._session is not None:
            self._session.close()
            self._session = None
