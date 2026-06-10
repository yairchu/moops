import shlex

import pytest

from moops import Group


def test_list_non_merged_anchor_parses_correctly() -> None:
    """Non-merged list: bare --add anchors each item; --factor VALUE follows it.
    Before the fix, --factor was flagged as unexpected and --add was not treated
    as the anchor, so parsing returned an empty list."""
    g = Group(
        cli_args=["script.py", "--add", "--factor", "2", "--add", "--factor", "5"]
    )
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    iface = g.interface(ctrl)
    assert iface.missing_options() == []
    assert ctrl.value == [2.0, 5.0]


def test_list_non_merged_allows_following_sibling_options() -> None:
    """A non-merged list item should end before the next sibling option.

    The parser must not consume every later CLI token as part of the last list
    item; otherwise ordinary options after the list are rejected as item args.
    """
    g = Group(cli_args=["script.py", "--add", "--factor", "2", "--name", "Bob"])
    factors = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    iface = g.interface(factors, name)

    assert iface.missing_options() == []
    assert factors.value == [2.0]
    assert name.value == "Bob"


def test_list_non_merged_item_option_without_anchor_is_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A per-item option outside an anchor segment must not be silently ignored."""
    g = Group(cli_args=["script.py", "--factor", "2"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --factor" in capsys.readouterr().out


def test_list_non_merged_rejects_duplicate_scalar_item_option_in_segment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A single list item must not silently keep only the last scalar value."""
    g = Group(cli_args=["script.py", "--add", "--factor", "2", "--factor", "5"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "--factor was provided multiple times" in capsys.readouterr().out


def test_list_rejects_flag_item_controls() -> None:
    """Flag item controls are currently ambiguous and should fail fast."""
    g = Group(cli_args=["script.py"])

    with pytest.raises(ValueError, match=r"list.*value.*control"):
        g.list(
            option="--enabled",
            item=lambda grp: grp.switch(
                flag="--enabled",
                help_text="Enable item",
            ),
            help_text="Enabled items",
            value=[],
        )


def test_list_current_args_keeps_items_equal_to_item_default() -> None:
    """List items equal to the item control's default are still list data.

    Before the fix, rendering delegated to item_control.format_value(), which
    omitted default-valued items and changed [1.0, 2.0] into just [2.0]."""
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[1.0, 2.0],
    )
    iface = g.interface(ctrl)

    assert iface._current_args() == "--factor 1.0 --factor 2.0"  # type: ignore[attr-defined]


def test_list_current_args_round_trips_default_item_starting_with_dash() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--word",
        item=lambda grp: grp.text(value="-x", option="--word", help_text="Word"),
        help_text="Words",
        value=["-x"],
    )
    current_args = g.interface(ctrl)._current_args()  # type: ignore[attr-defined]

    target = Group(cli_args=["script.py", *shlex.split(current_args)])
    target_ctrl = target.list(
        option="--word",
        item=lambda grp: grp.text(value="-x", option="--word", help_text="Word"),
        help_text="Words",
        value=[],
    )

    target.interface(target_ctrl)

    assert target_ctrl.value == ["-x"]


def test_script_callout_command_wraps_long_list_options() -> None:
    """The script-callout command should wrap, even for a single list control.

    A list emits its whole repeated sequence as one option group, so the
    per-group wrapping kept it all on a single overflowing line. The wrapped
    command should break long lines instead of producing one giant line."""
    from moops._text_wrap import wrap_command

    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[float(n) for n in range(1, 11)],
    )
    iface = g.interface(ctrl)

    command = wrap_command("script.py", iface._arg_groups())  # type: ignore[attr-defined]
    longest = max(len(line) for line in command.splitlines())
    assert longest <= 72, command
