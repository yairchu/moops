import pytest

from moops import Group


def test_help_exits_zero():
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.render_cli(ctrl)
    assert exc_info.value.code == 0


def test_invalid_arg_exits_nonzero():
    g = Group(cli_args=["script.py", "--unknown"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.render_cli(ctrl)
    assert exc_info.value.code != 0
