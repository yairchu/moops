"""Focused tests for the Kitty graphics protocol framing in _terminal_graphics.

The chunking and control-key placement are easy to get subtly wrong (a stray
control key on a continuation chunk, or a botched 4096-byte boundary corrupts
the image), so they are pinned here.
"""

import base64
import io
import re
import typing

from moops import _terminal_graphics as tg

_APC = re.compile(r"\033_G(?P<controls>[^;]*);(?P<payload>[^\033]*)\033\\")


def _parse(sequence: str) -> list[tuple[dict[str, str], str]]:
    chunks: list[tuple[dict[str, str], str]] = []
    for match in _APC.finditer(sequence):
        controls = dict(
            part.split("=", 1) for part in match["controls"].split(",") if part
        )
        chunks.append((controls, match["payload"]))
    return chunks


def test_single_chunk_framing() -> None:
    chunks = _parse(tg.kitty_sequence(b"tiny"))
    assert len(chunks) == 1
    controls, payload = chunks[0]
    # transmit-and-display a PNG, and a lone chunk is also the final one.
    assert controls == {"a": "T", "f": "100", "m": "0"}
    assert base64.standard_b64decode(payload) == b"tiny"


def test_multi_chunk_reassembles_and_marks_continuations() -> None:
    png = bytes(range(256)) * 60  # base64 spans several 4096-byte chunks
    chunks = _parse(tg.kitty_sequence(png))
    assert len(chunks) > 1
    # Image controls ride only on the first chunk; the rest carry just `m`.
    assert chunks[0][0] == {"a": "T", "f": "100", "m": "1"}
    assert all(controls == {"m": "1"} for controls, _ in chunks[1:-1])
    assert chunks[-1][0] == {"m": "0"}
    assert all(len(payload) <= 4096 for _, payload in chunks)
    rejoined = base64.standard_b64decode("".join(p for _, p in chunks))
    assert rejoined == png


def test_cols_scales_only_first_chunk() -> None:
    controls, _ = _parse(tg.kitty_sequence(b"x" * 5000, cols=40))[0]
    assert controls["c"] == "40"


class _FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def _fixed(protocol: tg.Protocol) -> typing.Callable[..., tg.Protocol]:
    def detect(**_: typing.Any) -> tg.Protocol:
        return protocol

    return detect


def test_detect_requires_a_terminal() -> None:
    not_a_tty = io.StringIO()
    assert tg.detect(env={"TERM": "xterm-kitty"}, stream=not_a_tty) is tg.Protocol.NONE


def test_detect_identifies_kitty_family() -> None:
    cases: list[dict[str, str]] = [
        {"TERM": "xterm-kitty"},
        {"KITTY_WINDOW_ID": "1"},
        {"TERM": "xterm-ghostty"},
        {"TERM_PROGRAM": "WezTerm"},
        {"KONSOLE_VERSION": "240400"},
    ]
    for env in cases:
        assert tg.detect(env=env, stream=_FakeTTY()) is tg.Protocol.KITTY, env
    assert tg.detect(env={"TERM": "dumb"}, stream=_FakeTTY()) is tg.Protocol.NONE


def test_emit_skips_escapes_when_unsupported(
    monkeypatch: typing.Any, capsys: typing.Any
) -> None:
    monkeypatch.setattr(tg, "detect", _fixed(tg.Protocol.NONE))
    stream = _FakeTTY()
    tg.emit(b"png-bytes", stream=stream)
    assert stream.getvalue() == ""  # no escape sequence leaked to the stream
    assert "no inline-image support" in capsys.readouterr().out


def test_emit_writes_sequence_when_supported(monkeypatch: typing.Any) -> None:
    monkeypatch.setattr(tg, "detect", _fixed(tg.Protocol.KITTY))
    stream = _FakeTTY()
    tg.emit(b"png-bytes", stream=stream)
    assert stream.getvalue() == tg.kitty_sequence(b"png-bytes") + "\n"
