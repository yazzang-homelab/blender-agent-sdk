"""Wire format shared by the client and the in-Blender bridge.

Every message is a 4-byte big-endian unsigned length followed by that many
bytes of UTF-8 JSON. Requests are ``{"id", "method", "params"}``; responses are
``{"id", "ok": true, "result"}`` or ``{"id", "ok": false, "error": {"type",
"message", "traceback"}}``.

This module is imported both by normal Python and by Blender's bundled
interpreter, so it depends on the standard library only.
"""

import json
import struct

MAX_FRAME_BYTES = 64 * 1024 * 1024
_HEADER = struct.Struct(">I")


class ProtocolError(Exception):
    """The peer sent bytes that are not a valid frame."""


class ConnectionClosed(ProtocolError):
    """The peer closed the connection, possibly mid-frame."""


class FrameTooLarge(ProtocolError):
    """A frame exceeds MAX_FRAME_BYTES. Incoming: the stream cannot be resynchronised."""


class InvalidPayload(ProtocolError):
    """A complete frame whose payload is not UTF-8 JSON. The stream stays in sync."""


def encode_frame(message):
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_FRAME_BYTES:
        raise FrameTooLarge(f"frame of {len(payload)} bytes exceeds MAX_FRAME_BYTES={MAX_FRAME_BYTES}")
    return _HEADER.pack(len(payload)) + payload


def send_frame(sock, message):
    sock.sendall(encode_frame(message))


def _recv_exact(sock, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(min(remaining, 1 << 20))
        if not chunk:
            raise ConnectionClosed(f"connection closed with {remaining} of {size} bytes outstanding")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_frame(sock):
    """Read one complete frame. Partial reads are reassembled; a socket timeout propagates."""
    header = sock.recv(_HEADER.size)
    if not header:
        raise ConnectionClosed("connection closed")
    if len(header) < _HEADER.size:
        header += _recv_exact(sock, _HEADER.size - len(header))
    (size,) = _HEADER.unpack(header)
    if size > MAX_FRAME_BYTES:
        raise FrameTooLarge(f"incoming frame of {size} bytes exceeds MAX_FRAME_BYTES={MAX_FRAME_BYTES}")
    payload = _recv_exact(sock, size)
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidPayload(f"invalid JSON payload: {exc}") from exc


__all__ = [
    "MAX_FRAME_BYTES",
    "ConnectionClosed",
    "FrameTooLarge",
    "InvalidPayload",
    "ProtocolError",
    "encode_frame",
    "recv_frame",
    "send_frame",
]
