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


def test_switch_with_default_true_and_explicit_flag():
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(value=True, flag="--no-verbose", help_text="Disable verbose output")
    assert ctrl.value is True


def test_switch_override_uses_base_option_name():
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("x", overrides={"verbose": False})
    ctrl = sub.switch(value=True, label="Verbose", help_text="Enable verbose")
    assert ctrl.value is False


def test_label_derived_from_option_has_no_leading_spaces():
    g = Group(cli_args=["script.py"])
    ctrl = g.text(option="--my-option", help_text="Some option")
    label = g._state.control_meta[id(ctrl)].opt.label
    assert not label.startswith(" ")


def test_duplicate_control_error_mentions_render_cli():
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    method = g.render_cli
    with pytest.raises(ValueError, match=method.__name__):
        method(ctrl, ctrl)


def test_subgroup_prefixes_options():
    g = Group(cli_args=["script.py", "--casing-style", "snake_case"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    assert ctrl.value == "snake_case"


def test_subgroup_render_cli_is_noop():
    g = Group(cli_args=["script.py"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case"], label="Style", help_text="...", allow_select_none=False
    )
    casing.render_cli(ctrl)  # should not exit


def test_subgroup_controls_visible_in_parent_help(capsys):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.render_cli(ctrl)
    assert "--casing-style" in capsys.readouterr().out


def test_equals_flag_not_consumed_as_prefix_for_next_arg(capsys):
    g = Group(cli_args=["script.py", "--name=Alice", "unexpected"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.render_cli(ctrl)
    # "unexpected" should be reported as the bad argument, not silently consumed
    assert "unexpected" in capsys.readouterr().out


def test_dropdown_no_flag_selects_none():
    g = Group(cli_args=["script.py", "--no-style"])
    ctrl = g.dropdown(
        ["snake_case", "camel_case"],
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    assert ctrl.value is None


def test_dropdown_no_flag_and_value_is_error(capsys):
    g = Group(cli_args=["script.py", "--no-style", "--style", "snake_case"])
    ctrl = g.dropdown(
        ["snake_case", "camel_case"],
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    with pytest.raises(SystemExit) as exc_info:
        g.render_cli(ctrl)
    assert exc_info.value.code != 0
    assert "--no-style" in capsys.readouterr().out


def test_validation_error_not_shown_for_unrendered_control(capsys):
    g = Group(cli_args=["script.py", "--count", "not-a-number"])
    _unrendered = g.number(option="--count", help_text="A count")
    other = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit):
        g.render_cli(other)
    assert "Unexpected argument: --count" in capsys.readouterr().out


def test_help_usage_line_has_no_double_spaces(capsys):
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.render_cli(ctrl)  # no flags, only an option
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "  " not in usage_line
