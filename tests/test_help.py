import pytest

from moops import Group


def test_help_exits_zero() -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code == 0


def test_subgroup_controls_visible_in_parent_help(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.interface(casing.interface(ctrl))
    assert "--casing-style" in capsys.readouterr().out


def test_overridden_control_not_in_help(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing", overrides={"style": "snake_case"})
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.interface(casing.interface(ctrl))
    assert "--casing-style" not in capsys.readouterr().out


def test_help_usage_line_has_no_double_spaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.interface(ctrl)  # no flags, only an option
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "  " not in usage_line


def test_help_option_lines_wrap_at_88_columns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.text(
        option="--long-option-name",
        help_text="A help text long enough to overflow eighty-eight columns",
    )
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    out = capsys.readouterr().out
    option_lines = [line for line in out.splitlines() if line.startswith("  --")]
    assert all(len(line) <= 88 for line in option_lines)


def test_standalone_option_after_variant_group_is_separated_in_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A standalone option that follows variant group sections must be separated
    by a blank line, not run on as if it belongs to the last variant group."""
    g = Group(cli_args=["script.py", "--help"])
    mode = g.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="Travel mode",
        allow_select_none=False,
    )
    travel = g.variant("travel", mode)
    distance = travel["car"].number(value=120, option="--distance", help_text="Miles")
    tickets = travel["train"].number(value=2, option="--tickets", help_text="Tickets")
    extra = g.checkbox(label="Extra", help_text="Standalone option")

    with pytest.raises(SystemExit):
        g.interface(
            mode,
            travel["car"].interface(distance),
            travel["train"].interface(tickets),
            extra,
        )

    lines = capsys.readouterr().out.splitlines()
    [_usage_idx, extra_idx] = [i for i, line in enumerate(lines) if "--extra" in line]
    # standalone option must be separated from the last variant group by a blank line
    assert lines[extra_idx - 1] == ""


def test_no_options_usage_omits_interactive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With no controls there is nothing to prompt for, so --interactive is
    inert and should not be advertised in the usage line."""
    g = Group(cli_args=["script.py", "--help"])
    with pytest.raises(SystemExit):
        g.interface()
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "--interactive" not in usage_line


def test_empty_interface_omits_usage_block() -> None:
    rendered = Group(cli_args=["script.py"]).interface()._mime_()[1]  # type: ignore[misc]
    assert "Usage:" not in rendered
    assert "details" not in rendered


def test_short_usage_is_not_wrapped_in_disclosure() -> None:
    g = Group(cli_args=["script.py"])
    iface = g.interface(g.text(label="Name", help_text="A name"))

    rendered = iface._mime_()[1]  # type: ignore[misc]
    assert "details" not in rendered
    assert "Usage:" in rendered


def test_long_usage_disclosure_stays_closed() -> None:
    g = Group(cli_args=["script.py"])
    ctrls = [
        g.text(option=f"--option-number-{i}", help_text="An option") for i in range(4)
    ]
    iface = g.interface(*ctrls)

    rendered = iface._mime_()[1]  # type: ignore[misc]
    assert "details open" not in rendered
    assert "details" in rendered


def test_usage_wraps_at_88_columns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrls = [
        g.text(option=f"--option-number-{i}", help_text="An option") for i in range(8)
    ]
    with pytest.raises(SystemExit):
        g.interface(*ctrls)
    out = capsys.readouterr().out
    assert out.startswith("Usage:")
    usage_block_lines = out.split("\n\n")[0].splitlines()
    assert all(len(line) <= 88 for line in usage_block_lines)


def test_dropdown_no_flag_shown_as_mutex_in_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.dropdown(["a", "b"], value="a", label="Style", help_text="The style")
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "[--style {a|b} | --no-style]" in usage_line
