import pytest

from moops import Group


def test_help_exits_zero() -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code == 0


def test_invalid_arg_exits_nonzero() -> None:
    g = Group(cli_args=["script.py", "--unknown"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0


def test_switch_with_default_true_and_explicit_flag() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(value=True, flag="--no-verbose", help_text="Disable verbose output")
    assert ctrl.value is True


def test_switch_override_uses_base_option_name() -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("x", overrides={"verbose": False})
    ctrl = sub.switch(value=True, label="Verbose", help_text="Enable verbose")
    assert ctrl.value is False


def test_label_derived_from_option_has_no_leading_spaces() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.text(option="--my-option", help_text="Some option")
    label = g._state.control_meta[id(ctrl)].cli.opt.label  # type: ignore
    assert not label.startswith(" ")


def test_duplicate_control_error_mentions_interface() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    method = g.interface
    with pytest.raises(ValueError, match=method.__name__):
        method(ctrl, ctrl)


def test_subgroup_prefixes_options() -> None:
    g = Group(cli_args=["script.py", "--casing-style", "snake_case"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    assert ctrl.value == "snake_case"


@pytest.mark.xfail(
    reason="TODO: subgroup() ignores parent prefix, nested prefixes don't accumulate"
)
def test_nested_subgroup_accumulates_prefix() -> None:
    g = Group(cli_args=["script.py", "--outer-inner-style", "snake_case"])
    outer = g.subgroup("outer")
    inner = outer.subgroup("inner")
    ctrl = inner.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    assert ctrl.value == "snake_case"


def test_subgroup_interface_is_noop():
    g = Group(cli_args=["script.py"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case"], label="Style", help_text="...", allow_select_none=False
    )
    casing.interface(ctrl)  # should not exit


def test_subgroup_controls_visible_in_parent_help(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    assert "--casing-style" in capsys.readouterr().out


def test_overridden_control_not_in_help(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing", overrides={"style": "snake_case"})
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    assert "--casing-style" not in capsys.readouterr().out


def test_equals_flag_not_consumed_as_prefix_for_next_arg(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--name=Alice", "unexpected"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    # "unexpected" should be reported as the bad argument, not silently consumed
    assert "unexpected" in capsys.readouterr().out


def test_dropdown_no_flag_selects_none() -> None:
    g = Group(cli_args=["script.py", "--no-style"])
    ctrl = g.dropdown(
        ["snake_case", "camel_case"],
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    assert ctrl.value is None


def test_dropdown_no_flag_and_value_is_error(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--no-style", "--style", "snake_case"])
    ctrl = g.dropdown(
        ["snake_case", "camel_case"],
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0
    assert "--no-style" in capsys.readouterr().out


def test_validation_error_not_shown_for_unrendered_control(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--count", "not-a-number"])
    _unrendered = g.number(option="--count", help_text="A count")
    other = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit):
        g.interface(other)
    assert "Unexpected argument: --count" in capsys.readouterr().out


def test_number_accepts_negative_value() -> None:
    g = Group(cli_args=["script.py", "--count", "-3"])
    ctrl = g.number(option="--count", help_text="A count")
    g.interface(ctrl)
    assert ctrl.value == -3


def test_help_usage_line_has_no_double_spaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.interface(ctrl)  # no flags, only an option
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "  " not in usage_line
