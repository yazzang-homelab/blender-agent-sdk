"""Show PNG screenshots inside a terminal, using only the standard library.

``render(png)`` picks the best protocol the terminal supports:

* kitty graphics protocol (kitty, Ghostty, WezTerm) and iTerm2 inline images send the
  PNG itself, so the picture is shown at full resolution;
* everything else, tmux and SSH sessions included, gets Unicode half blocks in 24-bit
  color: two pixels per character cell, which any truecolor terminal can show.
"""

import base64
import os
import struct
import zlib

__all__ = ["decode_png", "halfblocks", "inline_protocol", "render"]

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}  # color type -> samples per pixel


def decode_png(data):
    """Decode a non-interlaced 8-bit PNG into ``(width, height, rows)`` of RGB tuples."""
    if not data.startswith(_SIGNATURE):
        raise ValueError("not a PNG file")
    pos, idat, header, palette = len(_SIGNATURE), [], None, None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("PNG has no IHDR chunk")
    width, height, depth, color, _, _, interlace = header
    if depth != 8 or interlace or color not in (*_CHANNELS, 3):
        raise ValueError(f"unsupported PNG (bit depth {depth}, color type {color}, interlace {interlace})")
    channels = 1 if color == 3 else _CHANNELS[color]
    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    rows, previous = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        line = _unfilter(raw[start], bytearray(raw[start + 1:start + 1 + stride]), previous, channels)
        previous = line
        if color == 3:
            rows.append([palette[i] for i in line])
        elif channels >= 3:
            rows.append([tuple(line[i:i + 3]) for i in range(0, stride, channels)])
        else:  # gray, gray + alpha
            rows.append([(line[i],) * 3 for i in range(0, stride, channels)])
    return width, height, rows


def _unfilter(kind, line, prev, bpp):
    if kind == 0:
        return line
    for i in range(len(line)):
        left = line[i - bpp] if i >= bpp else 0
        up = prev[i]
        if kind == 1:
            line[i] = (line[i] + left) & 0xFF
        elif kind == 2:
            line[i] = (line[i] + up) & 0xFF
        elif kind == 3:
            line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
        elif kind == 4:
            upper_left = prev[i - bpp] if i >= bpp else 0
            p = left + up - upper_left
            pa, pb, pc = abs(p - left), abs(p - up), abs(p - upper_left)
            pred = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
            line[i] = (line[i] + pred) & 0xFF
        else:
            raise ValueError(f"bad PNG filter type {kind}")
    return line


def halfblocks(png, columns=80):
    """The image as rows of ``▀`` cells: foreground = upper pixel, background = lower pixel."""
    width, height, rows = decode_png(png)
    columns = max(1, min(columns, width))
    lines = max(1, round(height * columns / width / 2))
    out = []
    for cell_y in range(lines):
        parts = []
        for cell_x in range(columns):
            x = min(width - 1, cell_x * width // columns)
            top = rows[min(height - 1, (2 * cell_y) * height // (2 * lines))][x]
            bottom = rows[min(height - 1, (2 * cell_y + 1) * height // (2 * lines))][x]
            parts.append("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀" % (*top, *bottom))
        out.append("".join(parts) + "\x1b[0m")
    return "\n".join(out)


def inline_protocol(env=None):
    """``"kitty"``, ``"iterm2"`` or ``None`` for the terminal described by ``env``."""
    env = os.environ if env is None else env
    if env.get("TMUX") or env.get("TERM", "").startswith("screen"):
        return None  # multiplexers drop these escapes unless passthrough is configured
    term, program = env.get("TERM", ""), env.get("TERM_PROGRAM", "")
    if "kitty" in term or env.get("KITTY_WINDOW_ID") or program in ("ghostty", "WezTerm"):
        return "kitty"
    if program == "iTerm.app" or env.get("LC_TERMINAL") == "iTerm2":
        return "iterm2"
    return None


def render(png, columns=80, env=None):
    """Escape sequences that draw ``png`` in the terminal, ``columns`` cells wide."""
    protocol = inline_protocol(env)
    if protocol == "kitty":
        payload = base64.b64encode(png).decode("ascii")
        chunks = [payload[i:i + 4096] for i in range(0, len(payload), 4096)] or [""]
        out = []
        for i, chunk in enumerate(chunks):
            more = 1 if i < len(chunks) - 1 else 0
            keys = f"a=T,f=100,c={columns}," if i == 0 else ""
            out.append(f"\x1b_G{keys}m={more};{chunk}\x1b\\")
        return "".join(out) + "\n"
    if protocol == "iterm2":
        payload = base64.b64encode(png).decode("ascii")
        return f"\x1b]1337;File=inline=1;width={columns};size={len(png)}:{payload}\a\n"
    return halfblocks(png, columns) + "\n"
