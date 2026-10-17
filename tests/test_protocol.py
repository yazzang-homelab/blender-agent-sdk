import socket
import struct
import threading

import pytest

from blender_agent import protocol as wire


def test_roundtrip_unicode():
    a, b = socket.socketpair()
    with a, b:
        wire.send_frame(a, {"id": 1, "name": "큐브 ✓"})
        assert wire.recv_frame(b) == {"id": 1, "name": "큐브 ✓"}


def test_frame_split_into_single_bytes_is_reassembled():
    a, b = socket.socketpair()
    frame = wire.encode_frame({"id": 7, "payload": "x" * 5000})

    def trickle():
        for i in range(len(frame)):
            a.sendall(frame[i:i + 1])

    with a, b:
        t = threading.Thread(target=trickle)
        t.start()
        assert wire.recv_frame(b) == {"id": 7, "payload": "x" * 5000}
        t.join()


def test_two_frames_in_one_write_are_separated():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(wire.encode_frame({"n": 1}) + wire.encode_frame({"n": 2}))
        assert wire.recv_frame(b) == {"n": 1}
        assert wire.recv_frame(b) == {"n": 2}


def test_oversized_header_is_rejected_without_reading_payload():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(struct.pack(">I", wire.MAX_FRAME_BYTES + 1))
        with pytest.raises(wire.ProtocolError, match="exceeds"):
            wire.recv_frame(b)


def test_close_mid_frame_raises_connection_closed():
    a, b = socket.socketpair()
    with b:
        a.sendall(wire.encode_frame({"id": 1})[:6])
        a.close()
        with pytest.raises(wire.ConnectionClosed):
            wire.recv_frame(b)


def test_invalid_json_payload():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(struct.pack(">I", 3) + b"{x}")
        with pytest.raises(wire.ProtocolError, match="invalid JSON"):
            wire.recv_frame(b)


def test_side_effect_turns_a_success_into_an_error():
    ok = {"id": 7, "ok": True, "result": {"scene": "Scene"}}
    reported = wire.report_side_effect(ok, "FreestyleDisabled", "Freestyle was turned off")
    assert reported == wire.error_response(7, "FreestyleDisabled",
                                           "Freestyle was turned off (the request itself completed)")


def test_side_effect_keeps_the_original_failure():
    failed = wire.error_response(7, "RuntimeError", "append failed", "Traceback ...")
    reported = wire.report_side_effect(failed, "FreestyleDisabled", "Freestyle was turned off")
    assert reported["error"] == {"type": "RuntimeError", "traceback": "Traceback ...",
                                 "message": "append failed (also: Freestyle was turned off)"}
    assert failed["error"]["message"] == "append failed"  # not mutated
