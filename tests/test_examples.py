import pathlib
import subprocess
import sys

import pytest

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


def test_variant_embed_help_lists_all_notebook_branches() -> None:
    result = subprocess.run(
        [sys.executable, "examples/variant_embed.py", "-h"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Options for --notebook name-casing" in result.stdout
    assert "Options for --notebook word-count" in result.stdout


def test_variant_embed_invalid_args_do_not_emit_child_output() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "examples/variant_embed.py",
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
