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
    if args == ("--help",):
        assert "Usage:" in result.stdout
