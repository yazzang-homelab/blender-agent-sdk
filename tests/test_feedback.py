"""Terminal previews, the screenshot gallery and the long-lived Studio session."""

import json
import struct
import urllib.request
import zlib

import pytest

from blender_agent import termimg
from blender_agent.studio import Gallery, Studio


def _png(width, height, pixels, filters):
    """Encode RGB rows with the given per-row filter types (0-4), like a real encoder would."""
    raw, prev = b"", bytes(width * 3)
    for y in range(height):
        line = bytes(c for px in pixels[y] for c in px)
        kind = filters[y % len(filters)]
        out = bytearray()
        for i, value in enumerate(line):
            left = line[i - 3] if i >= 3 else 0
            up = prev[i]
            upper_left = prev[i - 3] if i >= 3 else 0
            if kind == 1:
                value -= left
            elif kind == 2:
                value -= up
            elif kind == 3:
                value -= (left + up) >> 1
            elif kind == 4:
                p = left + up - upper_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - upper_left)
                value -= left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
            out.append(value & 0xFF)
        raw += bytes([kind]) + bytes(out)
        prev = line

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PIXELS = [[((x * 37 + y * 11) % 256, (x * 5) % 256, (y * 53) % 256) for x in range(7)] for y in range(6)]


@pytest.mark.parametrize("filters", [[0], [1], [2], [3], [4], [0, 1, 2, 3, 4]])
def test_png_decoder_undoes_every_filter(filters):
    width, height, rows = termimg.decode_png(_png(7, 6, PIXELS, filters))
    assert (width, height) == (7, 6)
    assert rows == PIXELS


def test_halfblocks_pack_two_pixel_rows_per_line():
    pixels = [[(255, 0, 0)] * 4, [(0, 0, 255)] * 4]
    text = termimg.halfblocks(_png(4, 2, pixels, [0]), columns=4)
    assert text.count("\n") == 0 and text.count("▀") == 4
    assert "\x1b[38;2;255;0;0m\x1b[48;2;0;0;255m▀" in text


@pytest.mark.parametrize("env, expected", [
    ({"TERM": "xterm-kitty"}, "kitty"),
    ({"TERM_PROGRAM": "WezTerm"}, "kitty"),
    ({"TERM_PROGRAM": "iTerm.app"}, "iterm2"),
    ({"TERM": "xterm-kitty", "TMUX": "/tmp/tmux-1/default,1,0"}, None),
    ({"TERM": "xterm-256color"}, None),
])
def test_inline_protocol_detection(env, expected):
    assert termimg.inline_protocol(env) == expected


def test_inline_protocols_carry_the_png_itself():
    png = _png(7, 6, PIXELS, [0])
    kitty = termimg.render(png, 20, env={"TERM": "xterm-kitty"})
    assert kitty.startswith("\x1b_Ga=T,f=100,c=20,m=0;")
    iterm = termimg.render(png, 20, env={"TERM_PROGRAM": "iTerm.app"})
    assert f"size={len(png)}" in iterm


def test_blender_screenshots_decode(session):
    png, meta = session.screenshot(64, 48)
    width, height, rows = termimg.decode_png(png)
    assert (width, height) == (meta["width"], meta["height"])
    assert len(rows) == 48 and len(rows[0]) == 64


def test_gallery_records_serves_and_survives_restart(tmp_path):
    png = _png(7, 6, PIXELS, [0])
    gallery = Gallery(tmp_path / "g", title="demo")
    first = gallery.add(png, "first")
    second = gallery.add(png, "added <hat>")
    assert (first["n"], second["n"]) == (1, 2)
    assert (tmp_path / "g" / "latest.png").read_bytes() == png
    page = (tmp_path / "g" / "index.html").read_text(encoding="utf-8")
    assert "added &lt;hat&gt;" in page and 'http-equiv="refresh"' in page
    server = gallery.serve()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/latest.png", timeout=5) as resp:
            assert resp.read() == png
    finally:
        server.shutdown()
        server.server_close()
    again = Gallery(tmp_path / "g")
    assert again.add(png, "third")["n"] == 3
    assert [json.loads(line)["label"] for line in (tmp_path / "g" / "history.jsonl").read_text().splitlines()] == [
        "first", "added <hat>", "third"]


def test_studio_keeps_one_session_and_recovers_from_a_crash(blender_bin, tmp_path):
    studio = Studio(Gallery(tmp_path / "g"), blender=blender_bin, allow_exec=True)
    try:
        assert studio.run("call_operator", {"idname": "mesh.primitive_monkey_add"})["ok"]
        names = {o["name"] for o in studio.run("scene_graph", {})["result"]["objects"]}
        assert "Suzanne" in names  # same Blender across calls
        shot = studio.run("screenshot", {"width": 32, "height": 24}, label="monkey")
        assert shot["shot"]["n"] == 1 and shot["shot"]["label"] == "monkey"
        lost = studio.run("exec_python", {"code": "import os; os._exit(3)"})  # Blender crashes
        assert not lost["ok"] and "will restart" in lost["error"]
        after = studio.run("scene_graph", {})
        assert after["ok"] and studio.restarts == 1
        assert "Suzanne" not in {o["name"] for o in after["result"]["objects"]}
    finally:
        studio.close()
