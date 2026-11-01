import importlib.util
import pathlib

import pytest

import moops


def test_run_rejects_interface_displayed_with_its_controls(
    tmp_path: pathlib.Path,
) -> None:
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
    spec = importlib.util.spec_from_file_location("same_cell", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(
        RuntimeError,
        match="display `interface` from a cell other than "
        "the one creating its controls",
    ):
        moops.run(module)
