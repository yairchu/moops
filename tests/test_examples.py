import pathlib
import subprocess
import sys

import pytest

from examples.basics import sparse_mapping

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _notebook_scripts() -> list[pathlib.Path]:
    return [
        path.relative_to(ROOT)
        for path in sorted((ROOT / "examples").rglob("*.py"))
        if path.name != "__init__.py" and "app = marimo.App" in path.read_text()
    ]


@pytest.mark.parametrize("script", _notebook_scripts())
@pytest.mark.parametrize("args", [(), ("--help",)])
def test_example_notebooks_run_as_scripts(
    script: pathlib.Path, args: tuple[str, ...]
) -> None:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "UserWarning: " not in result.stderr, result.stderr
    if args == ("--help",):
        assert "Usage:" in result.stdout


def test_variant_embed_help_shows_only_active_branch() -> None:
    result = subprocess.run(
        [sys.executable, "examples/composition/variant_embed.py", "-h"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Options for --notebook name-casing" in result.stdout
    assert "Options for --notebook word-count" not in result.stdout


def test_variant_embed_selector_accepts_normalized_branch_key() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/composition/variant_embed.py",
            "--notebook",
            "word-count",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "Selected notebook result: `2`" in result.stdout


def test_variant_embed_invalid_args_do_not_emit_child_output() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/composition/variant_embed.py",
            "--notebook-word-count-test",
            "hi",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert "Unexpected argument: --notebook-word-count-test" in result.stdout
    assert "LoremIpsum" not in result.stdout


def test_variant_embed_inactive_branch_args_do_not_emit_child_output() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/composition/variant_embed.py",
            "--notebook-word-count-text",
            "hi",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode != 0
    assert "Unexpected argument: --notebook-word-count-text" in result.stdout
    assert "LoremIpsum" not in result.stdout


def test_sparse_mapping_state_read_is_upstream_of_mapping_control() -> None:
    """The mapping cell must rerun after its append callback updates state.

    Marimo does not rerun the cell that initiates a state update. Reading
    get_items in the same cell that passes set_items to composites.mapping
    therefore leaves the rendered editor unchanged when Append is clicked.
    """
    mapping_cell = next(
        data.cell
        for data in sparse_mapping.app._cell_manager.cell_data()  # pyright: ignore[reportPrivateUsage]
        if "composites.mapping(" in data.code
    )
    assert mapping_cell is not None

    assert "get_items" not in mapping_cell.refs
    assert {"items_value", "set_items"} <= mapping_cell.refs
