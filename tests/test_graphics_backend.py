"""Tests for the matplotlib GUI-backend switch behind ``Group.graphics_supported``."""

import concurrent.futures
import os
import pathlib
import subprocess
import sys
import typing

import matplotlib
import pytest

import moops
from moops import _terminal_graphics


def _make_figure() -> None:
    import matplotlib.pyplot as plt

    fig = plt.figure()  # type: ignore[reportUnknownMemberType]
    plt.close(fig)


def _cli_group() -> moops.Group:
    g = moops.Group(cli_args=["script.py"])
    g.output_mode = moops.OutputMode.STDOUT
    return g


def test_graphics_supported_enables_worker_thread_figures(
    monkeypatch: typing.Any,
) -> None:
    """Plotting gated on ``graphics_supported`` must work in worker threads.

    GUI backends (notably macOS's) refuse to create figures outside the main
    thread, so apps offloaded by ``run_in_thread_if_in_async`` (e.g. step
    notebooks run by a pipeline notebook) crash when they plot. A ``True``
    ``graphics_supported`` on the CLI means figures only get rasterized, so it
    switches to a non-GUI backend.
    """
    if sys.platform != "darwin":
        pytest.skip("Exercises the macOS GUI backend")
    original = matplotlib.get_backend()
    try:
        matplotlib.use("MacOSX")
    except ImportError:
        pytest.skip("MacOSX backend unavailable (no GUI session)")
    try:

        def _kitty(**_: typing.Any) -> bool:
            return True

        monkeypatch.setattr(_terminal_graphics, "detect", _kitty)
        assert _cli_group().graphics_supported
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(_make_figure).result()
    finally:
        matplotlib.use(original)


def test_graphics_supported_matplotlib_not_preimported() -> None:
    """The backend switch must not rely on matplotlib being imported already.

    When only the offloaded app imports matplotlib — inside the worker thread —
    the backend resolves there, picking the GUI backend on macOS and crashing.
    Runs in a subprocess to get an interpreter where matplotlib is not yet
    imported.
    """
    if sys.platform != "darwin":
        pytest.skip("Exercises the macOS GUI backend")
    code = """
import concurrent.futures
import sys

import moops
from moops import _terminal_graphics

assert "matplotlib" not in sys.modules

_terminal_graphics.detect = lambda **_: True
g = moops.Group(cli_args=["script.py"])
g.output_mode = moops.OutputMode.STDOUT
assert g.graphics_supported


def make_figure():
    import matplotlib.pyplot as plt

    fig = plt.figure()
    plt.close(fig)


with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
    executor.submit(make_figure).result()
"""
    src = pathlib.Path(__file__).parent.parent / "src"
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        env={**os.environ, "PYTHONPATH": str(src)},
    )
