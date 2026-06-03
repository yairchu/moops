"""Render figures as inline terminal images via the Kitty graphics protocol.

This backs ``Group.figure``/``Group.graphics_supported``. It is intentionally
free of any marimo or matplotlib import: notebook display is handled by the
caller, and figures are accepted by duck-typing so moops keeps no hard
dependency on a plotting library.
"""

from __future__ import annotations

import base64
import enum
import io
import os
import sys
import typing


class Protocol(enum.Enum):
    """Terminal image protocol detected for the current stdout."""

    KITTY = "kitty"
    NONE = "none"  # room for ITERM / SIXEL backends later


def detect(
    env: typing.Mapping[str, str] | None = None,
    stream: typing.IO[str] | None = None,
) -> Protocol:
    """Best-effort detection of inline-image support for ``stream``.

    Returns ``Protocol.NONE`` whenever stdout is not a terminal (piped or
    redirected), so escape sequences never leak into captured output. Terminal
    identification is by environment variable; this covers kitty, Ghostty,
    WezTerm, and Konsole, all of which speak the Kitty graphics protocol.
    """
    env = os.environ if env is None else env
    out = sys.stdout if stream is None else stream
    if out is None or not (hasattr(out, "isatty") and out.isatty()):
        return Protocol.NONE
    term = env.get("TERM", "")
    if (
        "KITTY_WINDOW_ID" in env
        or "kitty" in term
        or term == "xterm-ghostty"
        or "GHOSTTY_BIN_DIR" in env
        or env.get("TERM_PROGRAM") == "WezTerm"
        or "KONSOLE_VERSION" in env
    ):
        return Protocol.KITTY
    return Protocol.NONE


def to_png(fig: typing.Any, *, dpi: int | None = None) -> bytes:
    """Rasterize ``fig`` to PNG bytes by duck-typing common figure objects.

    Accepts raw PNG ``bytes`` (returned unchanged), a matplotlib ``Figure``
    (``savefig``), a matplotlib ``Axes`` (``get_figure``), or a PIL ``Image``
    (``save``).
    """
    if isinstance(fig, bytes):
        return fig
    buf = io.BytesIO()
    if hasattr(fig, "savefig"):  # matplotlib Figure
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    elif hasattr(fig, "get_figure"):  # matplotlib Axes
        fig.get_figure().savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    elif hasattr(fig, "save"):  # PIL Image
        fig.save(buf, format="PNG")
    else:
        raise TypeError(
            f"Don't know how to render {type(fig).__name__} to PNG; pass a "
            "matplotlib Figure/Axes, a PIL Image, or raw PNG bytes."
        )
    return buf.getvalue()


def kitty_sequence(png: bytes, *, cols: int | None = None) -> str:
    """Build the Kitty graphics APC sequence that transmits and displays a PNG.

    The base64-encoded payload is split into <=4096-byte chunks; every chunk
    but the last carries ``m=1`` (more data follows) and only the first chunk
    carries the image controls (``a=T`` transmit-and-display, ``f=100`` PNG,
    and an optional ``c=`` column count to scale into the cell grid).
    """
    payload = base64.standard_b64encode(png)
    step = 4096
    chunks = [payload[i : i + step] for i in range(0, len(payload), step)] or [b""]
    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        controls = ["a=T", "f=100"] + ([f"c={cols}"] if cols else []) if i == 0 else []
        controls.append(f"m={1 if i < len(chunks) - 1 else 0}")
        parts.append(f"\033_G{','.join(controls)};{chunk.decode('ascii')}\033\\")
    return "".join(parts)


def emit(png: bytes, *, stream: typing.IO[str] | None = None) -> None:
    """Write ``png`` to ``stream`` as an inline image, if the terminal supports it.

    When unsupported, prints a one-line notice instead of writing a file:
    callers are expected to gate on ``graphics_supported`` and provide their own
    fallback (e.g. ASCII art) when they want one.
    """
    out = sys.stdout if stream is None else stream
    if out is not None and detect(stream=out) is Protocol.KITTY:
        out.write(kitty_sequence(png) + "\n")
        out.flush()
    else:
        print(
            "[figure omitted: terminal has no inline-image support; "
            "gate with args.graphics_supported]"
        )
