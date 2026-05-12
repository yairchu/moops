import gc
import typing
import urllib.parse
import weakref

import marimo as mo
import pytest
from marimo._plugins.ui._core.ui_element import UIElement

import moops
from moops import Group, _input_map, _options


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


def test_switch_default_true_toggled_by_flag() -> None:
    g = Group(cli_args=["script.py", "--no-verbose"])
    ctrl = g.switch(value=True, flag="--no-verbose", help_text="Disable verbose output")
    assert ctrl.value is False


def test_switch_override_uses_base_option_name() -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("x", overrides={"verbose": False})
    ctrl = sub.switch(value=True, label="Verbose", help_text="Enable verbose")
    assert ctrl.value is False


def test_label_derived_from_option_has_no_leading_spaces() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.text(option="--my-option", help_text="Some option")
    assert not ctrl._args.label.startswith(" ")  # type: ignore


def test_duplicate_control_error_mentions_interface() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    method = g.interface
    with pytest.raises(ValueError, match="Duplicate"):
        method(ctrl, ctrl)


def test_subgroup_prefixes_options() -> None:
    g = Group(cli_args=["script.py", "--casing-style", "snake_case"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    assert ctrl.value == "snake_case"


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
        g.interface(casing.interface(ctrl))
    assert "--casing-style" in capsys.readouterr().out


def test_missing_subgroup_interface_warns_when_not_passed_to_parent() -> None:
    g = Group(cli_args=["script.py"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    _iface = casing.interface(ctrl)

    with pytest.warns(
        UserWarning,
        match=(
            "Controls registered with this Group "
            "but not passed to interface.*--casing-style"
        ),
    ):
        g.interface()


def test_missing_subgroup_interface_options_are_on_parent_interface() -> None:
    g = Group(cli_args=["script.py"])
    casing = g.subgroup("casing")
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    _iface = casing.interface(ctrl)

    with pytest.warns(UserWarning, match="--casing-style"):
        iface = g.interface()

    assert iface.missing_options() == ["--casing-style"]


def test_overridden_control_not_in_help(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--help"])
    casing = g.subgroup("casing", overrides={"style": "snake_case"})
    ctrl = casing.dropdown(
        ["snake_case", "camel_case"], label="Style", help_text="Text style"
    )
    with pytest.raises(SystemExit):
        g.interface(casing.interface(ctrl))
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


def test_text_area_from_stdin_flag_with_value_is_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--text-from-stdin=oops"])
    ctrl = g.text_area(option="--text", help_text="Input text")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0
    output = capsys.readouterr().out
    assert "--text-from-stdin does not take a value, but was given: oops" in output


def test_validation_error_not_shown_for_unrendered_control(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--count", "not-a-number"])
    _unrendered = g.number(option="--count", help_text="A count")
    other = g.switch(label="Verbose", help_text="Enable verbose output")
    warning_match = (
        "Controls registered with this Group but not passed to interface.*--count"
    )
    with (
        pytest.warns(
            UserWarning,
            match=warning_match,
        ),
        pytest.raises(SystemExit),
    ):
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


def test_dropdown_no_flag_shown_as_mutex_in_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.dropdown(["a", "b"], value="a", label="Style", help_text="The style")
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "[--style {a|b} | --no-style]" in usage_line


def test_cli_control_freed_when_control_gc_collected() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.slider(start=0, stop=10, value=3, label="Count", help_text="A count")
    cli = g.interface(ctrl).cli_map.get(ctrl)
    assert cli is not None
    cli_ref = weakref.ref(cli)
    del cli, ctrl
    gc.collect()
    assert cli_ref() is None


def test_interactive_ctrl_c_exits_cleanly(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_input(_prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    with pytest.raises(SystemExit) as exc_info:
        g.switch(label="Verbose", help_text="Enable verbose output")
    assert exc_info.value.code == 1
    assert "Aborted." in capsys.readouterr().out


def test_duplicate_subgroup_interface_raises_error() -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("x")
    ctrl = sub.switch(label="Verbose", help_text="Enable verbose output")
    iface = sub.interface(ctrl)
    with pytest.raises(ValueError, match="Duplicate"):
        g.interface(iface, iface)


def test_interactive_range_bad_numbers_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["10,abc", "20,80"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.range_slider(
        start=0, stop=100, value=[10, 50], label="Range", help_text="A range"
    )
    g.interface(ctrl)
    assert ctrl.value == [20, 80]


def test_composite_child_keeps_moops_metadata() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.slider(start=0, stop=10, value=3, label="Count", help_text="A count")
    cloned_ctrl = mo.ui.dictionary({"count": ctrl}).elements["count"]
    assert cloned_ctrl is not ctrl
    assert g.interface(cloned_ctrl).missing_options() == []


def test_option_named_file_does_not_conflict_with_marimo_notebook_param() -> None:
    class _MockCtrl:
        value = "some_file.txt"

    cli_map = _input_map.InputMap()
    ctrl = _MockCtrl()
    cli = _options.TextControl(
        option="--file", metavar="PATH", default="", help_text="x"
    )
    cli_map.register(ctrl, cli)

    interface = moops.Interface(
        controls=(ctrl,),
        cli_map=cli_map,
        notebook_file="notebook.py",
    )
    url = interface._standalone_url()  # type: ignore[attr-defined]
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["file"] == "notebook.py"
    assert params.get("file_") == "some_file.txt"


def test_custom_control_is_bound_to_wrapped_ui_element() -> None:
    g = Group(cli_args=["script.py"])
    fallback = g.range_slider(
        start=0,
        stop=10,
        value=[1, 9],
        option="--window",
        help_text="Window",
    )

    ctrl = g.custom(fallback, fallback)

    assert isinstance(ctrl, UIElement)
    assert typing.cast(typing.Any, ctrl)._id == typing.cast(typing.Any, fallback)._id
