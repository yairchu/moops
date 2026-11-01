import asyncio
import importlib.util
import pathlib
import subprocess
import sys
import types
import typing

import pytest
from marimo._ast.app import InternalApp
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import KernelStreams, NoopStream
from marimo._runtime.commands import AppMetadata
from marimo._runtime.context import get_context
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.context.types import teardown_context
from marimo._runtime.patches import create_main_module
from marimo._runtime.runner.hooks import NotebookCellHooks
from marimo._runtime.runtime import Kernel
from marimo._session.model import SessionMode

import moops


def _notebook(
    tmp_path: pathlib.Path,
    *,
    separate_display: bool = False,
    asynchronous: bool = False,
) -> types.ModuleType:
    path = tmp_path / "same_cell.py"
    path.write_text(
        """import marimo

app = marimo.App()

@app.cell
def _():
    import moops
    return (moops,)

@app.cell
def _(moops):
    args = moops.Group()
    return (args,)

@app.cell
def _(args):
    x = args.slider(0.0, 1.0, 0.1, value=0.5, option="--x", help_text="X")
    interface = args.interface(x)
    interface
    return (interface, x)

@app.cell
def _(x):
    result = x.value
    return (result,)

if __name__ == "__main__":
    app.run()
"""
    )
    source = path.read_text()
    if separate_display:
        source = source.replace("    interface\n", "")
        source += """

@app.cell
def _(interface):
    interface
    return
"""
    if asynchronous:
        source = source.replace("def _(args):", "async def _(args):")
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("same_cell", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("asynchronous", [False, True])
def test_run_rejects_interface_displayed_with_its_controls(
    tmp_path: pathlib.Path, asynchronous: bool
) -> None:
    module = _notebook(tmp_path, asynchronous=asynchronous)

    with pytest.raises(
        RuntimeError,
        match="display `interface` from a cell other than "
        "the one creating its controls",
    ):
        moops.run(module)


def test_script_rejects_interface_displayed_with_its_controls(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path)
    assert module.__file__ is not None
    completed = subprocess.run(
        [sys.executable, module.__file__],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode != 0
    assert (
        "display `interface` from a cell other than the one creating its controls"
        in completed.stderr
    )


def test_creating_interface_with_controls_is_valid_when_display_is_separate(
    tmp_path: pathlib.Path,
) -> None:
    # Only display reads values: building the Interface in the controls' cell
    # must remain valid, even though the script runner never renders it.
    module = _notebook(tmp_path, separate_display=True)
    assert moops.run(module) == 0.5


def test_run_from_event_loop_rejects_same_cell_display(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path, asynchronous=True)

    async def run() -> None:
        moops.run(module)

    with pytest.raises(RuntimeError, match="display `interface` from a cell other"):
        asyncio.run(run())


def test_kernel_render_names_interface_display_fix(tmp_path: pathlib.Path) -> None:
    module = _notebook(tmp_path)
    internal_app = InternalApp(module.app)
    streams = KernelStreams(stream=NoopStream(), stdout=None, stderr=None, stdin=None)
    kernel = Kernel(
        cell_configs={},
        app_metadata=AppMetadata(
            {}, {}, app_config=internal_app.config, filename=module.__file__
        ),
        user_config=DEFAULT_CONFIG,
        streams=streams,
        module=create_main_module(module.__file__, input_override=None),
        enqueue_control_request=lambda _: None,
        hooks=NotebookCellHooks(),
    )
    initialize_kernel_context(
        kernel=kernel, streams=streams, virtual_file_storage=None, mode=SessionMode.EDIT
    )
    try:
        ctx = get_context()
        cell_id = next(iter(internal_app.graph.cells))
        with ctx.with_cell_id(cell_id):
            args = moops.Group(cli_args=["script.py"])
            x = args.slider(0.0, 1.0, 0.1, value=0.5, option="--x", help_text="X")
            interface = args.interface(x)
            # Confirm this is the native marimo rule before checking moops'
            # rendering error in the same real kernel context.
            with pytest.raises(
                RuntimeError, match="Accessing the value of a UIElement"
            ):
                _ = x.value
            with pytest.raises(
                RuntimeError, match="display `interface` from a cell other"
            ):
                typing.cast(typing.Any, interface)._mime_()
    finally:
        teardown_context()
