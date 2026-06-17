import pytest

import moops
from moops import _status


def test_silenced_progress_bar_suppresses_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = moops.Group(cli_args=["script.py"])
    g.output_mode = None

    assert list(g.progress_bar([1, 2])) == [1, 2]
    assert capsys.readouterr().out == ""


def test_cli_progress_bar_range_uses_range_step(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(_status, "tqdm", None)
    g = moops.Group(cli_args=["script.py"])
    bar = g.progress_bar(range(0, 10, 2), total=10)

    assert list(bar) == [0, 2, 4, 6, 8]
    assert capsys.readouterr().out.splitlines()[-1] == "Progress: 10/10"
