"""Run many REA operations against one live Ghidra analysis.

Each ``rea <command>`` CLI invocation imports and auto-analyzes the target from
scratch (70 minutes for the 167 MB Blender 5.2.2 binary on a Ryzen AI 9 HX 370).
REA's stdio server keeps one analysis session open across calls, so this script
starts ``rea --mcp`` once and feeds it tool calls.

This is only how the reverse-engineering *tool* is driven; the blender-agent
SDK itself uses no MCP.

    python tools/rea_session.py list-tools
    python tools/rea_session.py serve QUEUE_DIR

``serve`` keeps the session alive and executes every ``QUEUE_DIR/<name>.req.json``
(``{"tool": ..., "arguments": {...}}``) in name order, writing ``<name>.res.json``.
Create ``QUEUE_DIR/stop`` to shut down.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


class Rea:
    def __init__(self):
        log = open(os.environ.get("REA_SESSION_LOG", "/tmp/rea-session.log"), "ab")
        self.proc = subprocess.Popen(["rea", "--mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=log, text=True, bufsize=1)
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "blender-agent-re", "version": "0.1"}})
        self.notify("notifications/initialized", {})

    def notify(self, method, params):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")

    def request(self, method, params):
        self.next_id += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next_id, "method": method,
                                          "params": params}) + "\n")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError(f"rea exited (code {self.proc.poll()}) during {method}")
            message = json.loads(line)
            if message.get("id") == self.next_id:
                if "error" in message:
                    return {"isError": True, "protocol_error": message["error"]}
                return message["result"]
            # server-initiated notifications (progress, logging) are ignored

    def call(self, tool, arguments):
        return self.request("tools/call", {"name": tool, "arguments": arguments})

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=120)


def serve(queue_dir):
    queue_dir.mkdir(parents=True, exist_ok=True)
    rea = Rea()
    (queue_dir / "ready").write_text(str(os.getpid()))
    try:
        while not (queue_dir / "stop").exists():
            pending = sorted(p for p in queue_dir.glob("*.req.json")
                             if not p.with_name(p.name.replace(".req.json", ".res.json")).exists())
            if not pending:
                time.sleep(1)
                continue
            req_path = pending[0]
            call = json.loads(req_path.read_text())
            started = time.time()
            result = rea.call(call["tool"], call.get("arguments", {}))
            result["_elapsed_s"] = round(time.time() - started, 1)
            res_path = req_path.with_name(req_path.name.replace(".req.json", ".res.json"))
            tmp = res_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(result, indent=1, ensure_ascii=False))
            tmp.rename(res_path)
    finally:
        rea.close()


def main():
    if sys.argv[1] == "list-tools":
        rea = Rea()
        try:
            for tool in rea.request("tools/list", {})["tools"]:
                print(json.dumps({"name": tool["name"], "description": tool.get("description", ""),
                                  "input": tool["inputSchema"]}, ensure_ascii=False))
        finally:
            rea.close()
    elif sys.argv[1] == "serve":
        serve(Path(sys.argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
