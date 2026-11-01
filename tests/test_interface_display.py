import asyncio
import importlib.util
import pathlib
import subprocess
import sys
import types

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

# marimo never reruns a control's defining cell when the control changes, so
# an Interface created there keeps showing the control's stale value.
SAME_CELL_ERROR = "Cannot create an Interface in a cell that creates its controls"

_CONTROLS_CELL = """
@app.cell
def _(args):
    x = args.slider(0.0, 1.0, 0.1, value=0.5, option="--x", help_text="X")
    return (x,)
"""

_INTERFACE_CELL = """
@app.cell
def _(args, x):
    interface = args.interface(x)
    interface
    return (interface,)
"""

_SAME_CELL = """
@app.cell
def _(args):
    x = args.slider(0.0, 1.0, 0.1, value=0.5, option="--x", help_text="X")
    interface = args.interface(x)
    return (interface, x)

@app.cell
def _(interface):
    interface
    return
"""


def _notebook(
    tmp_path: pathlib.Path,
    *,
    same_cell: bool,
    asynchronous: bool = False,
) -> types.ModuleType:
    """Write and import a notebook whose interface is created with or apart
    from its control."""
    body = _SAME_CELL if same_cell else _CONTROLS_CELL + _INTERFACE_CELL
    if asynchronous:
        body = body.replace("def _(args):", "async def _(args):")
    source = f"""import marimo

app = marimo.App()

@app.cell
def _():
    import moops
    return (moops,)

@app.cell
def _(moops):
    args = moops.Group()
    return (args,)
{body}
@app.cell
def _(x):
    result = x.value
    return (result,)

if __name__ == "__main__":
    app.run()
"""
    path = tmp_path / "notebook.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location("notebook", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("asynchronous", [False, True])
def test_run_rejects_interface_created_with_its_controls(
    tmp_path: pathlib.Path, asynchronous: bool
) -> None:
    module = _notebook(tmp_path, same_cell=True, asynchronous=asynchronous)

    with pytest.raises(RuntimeError, match=SAME_CELL_ERROR):
        moops.run(module)


def test_script_rejects_interface_created_with_its_controls(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path, same_cell=True)
    assert module.__file__ is not None
    completed = subprocess.run(
        [sys.executable, module.__file__],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode != 0
    assert SAME_CELL_ERROR in completed.stderr


def test_interface_in_its_own_cell_may_display_itself(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path, same_cell=False)
    assert moops.run(module) == 0.5


def test_run_from_event_loop_rejects_same_cell_creation(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path, same_cell=True, asynchronous=True)

    async def run() -> None:
        moops.run(module)

    with pytest.raises(RuntimeError, match=SAME_CELL_ERROR):
        asyncio.run(run())


def test_kernel_rejects_interface_created_with_its_controls(
    tmp_path: pathlib.Path,
) -> None:
    module = _notebook(tmp_path, same_cell=True)
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
            with pytest.raises(RuntimeError, match=SAME_CELL_ERROR):
                args.interface(x)
    finally:
        teardown_context()
