import asyncio
import dataclasses
import gc
import inspect
import pathlib
import shlex
import typing
import urllib.parse
import weakref

import marimo as mo
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from marimo._plugins.ui._core.ui_element import UIElement

import moops
import moops._control_mirroring as control_mirroring
import moops.group as group_module
from examples.composition import variant_trip
from moops import Group, _input_map, _options, _parse
from moops._custom_element import CustomElement


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


def test_label_parenthetical_unit_becomes_metavar(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.number(label="Length (seconds)", help_text="Clip length")

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--length SECONDS" in help_text
    assert "--length-(seconds)" not in help_text
    assert "LENGTH_(SECONDS)" not in help_text


def test_parenthetical_units_colliding_on_option_raise() -> None:
    g = Group(cli_args=["script.py"])
    secs = g.number(label="Length (seconds)", help_text="Clip length in seconds")
    mins = g.number(label="Length (minutes)", help_text="Clip length in minutes")

    with pytest.raises(ValueError, match=r"--length.*parenthetical"):
        g.interface(secs, mins)


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


def test_subgroup_warns_when_called_from_async_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_qp: typing.Any = {}
    monkeypatch.setattr(group_module.mo, "query_params", lambda: fake_qp)

    g = Group(cli_args=["script.py"])

    async def _async_cell() -> None:
        g.subgroup("casing")

    with pytest.warns(UserWarning, match="async cell"):
        asyncio.run(_async_cell())


def test_subgroup_markdown_demotes_headings_in_notebooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered: list[str] = []

    def fake_md(text: str) -> mo.Html:
        rendered.append(text)
        return typing.cast(mo.Html, object())

    # Patch before constructing: output_mode is set from running_in_notebook()
    # at construction, and the notebook branch of __init__ reads query_params().
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: dict[str, str]())
    monkeypatch.setattr(group_module.mo, "md", fake_md)

    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    sub.md("# Title\n## Section\n```\n# Not a title\n```\n####### Not a heading\n")

    assert rendered == [
        "## Title\n### Section\n```\n# Not a title\n```\n####### Not a heading\n"
    ]


def test_subgroup_markdown_demotes_headings_in_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    sub.md("# Title\n## Section\n```\n# Not a title\n```")

    assert (
        capsys.readouterr().out == "## Title\n### Section\n```\n# Not a title\n```\n\n"
    )


def test_subgroup_markdown_heading_offset_is_configurable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])
    same_level = g.subgroup("same", markdown_heading_offset=0)
    deeper = g.subgroup("deeper", markdown_heading_offset=2)

    same_level.md("# Same")
    deeper.md("# Deeper")

    assert capsys.readouterr().out == "# Same\n\n### Deeper\n\n"


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


def test_single_value_option_rejects_repeated_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--name", "Alice", "--name", "Bob"])
    ctrl = g.text(label="Name", help_text="A name")

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "--name was provided multiple times" in capsys.readouterr().out


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


def test_unbounded_number_none_value_round_trips() -> None:
    """An unbounded number can be cleared to None (marimo's number widget yields
    None when emptied), so that state must round-trip through the CLI instead of
    serializing to a bare ``--count None`` the parser then rejects. Bounded
    numbers and sliders coerce None to start, so this is specific to unbounded
    numbers."""
    source = Group(cli_args=["script.py"])
    count = source.number(value=5.0, option="--count", help_text="Count")
    count._value = None  # type: ignore[attr-defined]  # a cleared number input

    args = source.interface(count)._current_args()  # type: ignore[reportPrivateUsage]

    target = Group(
        cli_args=["script.py", *shlex.split(args)] if args else ["script.py"]
    )
    target_count = target.number(value=5.0, option="--count", help_text="Count")
    target.interface(target_count)

    assert target_count.value is None


def test_unbounded_number_none_value_standalone_query_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cleared (None) unbounded number must also round-trip through standalone
    query params rather than serializing to the literal string ``'None'``."""
    source = Group(cli_args=["script.py"])
    count = source.number(value=5.0, option="--count", help_text="Count")
    count._value = None  # type: ignore[attr-defined]
    query_values = source.interface(count)._standalone_query_values()  # type: ignore[reportPrivateUsage]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)

    target = Group(cli_args=["script.py"])
    target_count = target.number(value=5.0, option="--count", help_text="Count")

    assert target_count.value is None


def test_unbounded_number_allow_none_false_rejects_empty_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``allow_none=False`` should make cleared query state invalid/absent.

    The marimo widget can still be cleared, but moops should not persist that
    state in standalone query params or hydrate an empty query value as ``None``.
    """
    source = Group(cli_args=["script.py"])
    count = source.number(
        value=5.0,
        option="--count",
        help_text="Count",
        allow_none=False,
    )
    count._value = None  # type: ignore[attr-defined]

    assert source.interface(count)._standalone_query_values() == {}  # type: ignore[reportPrivateUsage]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: {"count": ""})

    target = Group(cli_args=["script.py"])
    target_count = target.number(
        value=5.0,
        option="--count",
        help_text="Count",
        allow_none=False,
    )

    assert target_count.value == 5.0
    assert target._state.validation_errors == {  # type: ignore[reportPrivateUsage]
        "--count": "Option --count expects a number, got: ''"
    }


def test_group_ui_method_signatures_match_marimo() -> None:
    group_names = {
        name for name, _ in inspect.getmembers(Group, predicate=inspect.isfunction)
    }
    marimo_names = {name for name in dir(mo.ui) if not name.startswith("_")}
    shared = group_names & marimo_names

    mismatches = {
        name: mismatches
        for name in shared
        for mismatches in [
            _signature_mismatches(getattr(Group, name), getattr(mo.ui, name))
        ]
        if mismatches
    }

    assert not mismatches, "\n".join(
        [
            "Group UI method signature mismatches:\n",
            *[
                f"{name}: {'; '.join(method_mismatches)}"
                for name, method_mismatches in mismatches.items()
            ],
        ]
    )


def _signature_mismatches(
    group_func: typing.Callable[..., typing.Any],
    marimo_func: typing.Callable[..., typing.Any],
) -> list[str]:
    [*group_params] = inspect.signature(group_func).parameters.values()
    if group_params and group_params[0].name == "self":
        group_params = group_params[1:]

    moops_only = {"flag", "option", "help_text"}
    group_params = [param for param in group_params if param.name not in moops_only]
    group_params_by_name = {
        param.name: param
        for param in group_params
        if param.kind
        not in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }
    }
    has_var_keyword = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in group_params
    )
    mismatches: list[str] = []

    group_index = 0
    past_unsupported_disabled = False
    for mo_param in inspect.signature(marimo_func).parameters.values():
        if mo_param.kind is inspect.Parameter.KEYWORD_ONLY:
            g_param = group_params_by_name.get(mo_param.name)
            if g_param is None:
                if has_var_keyword:
                    continue
                mismatches.append(f"missing keyword-only param {mo_param.name!r}")
                continue
            mismatches.extend(_param_mismatches(group_func.__name__, g_param, mo_param))
            continue
        if (
            mo_param.name == "disabled"
            and group_index < len(group_params)
            and group_params[group_index].name != "disabled"
        ):
            past_unsupported_disabled = True
            continue
        if past_unsupported_disabled and mo_param.kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }:
            continue
        if group_index >= len(group_params):
            mismatches.append(f"missing param {mo_param.name!r} at index {group_index}")
            continue
        g_param = group_params[group_index]
        if g_param.kind is inspect.Parameter.VAR_POSITIONAL:
            return mismatches
        if g_param.kind is inspect.Parameter.VAR_KEYWORD:
            return mismatches
        if g_param.kind is not mo_param.kind or g_param.name != mo_param.name:
            mismatches.append(
                f"index {group_index}: expected "
                f"{mo_param.kind.name} {mo_param.name!r}, "
                f"got {g_param.kind.name} {g_param.name!r}"
            )
            group_index += 1
            continue
        mismatches.extend(_param_mismatches(group_func.__name__, g_param, mo_param))
        group_index += 1
    return mismatches


def _param_mismatches(
    group_method_name: str,
    group_param: inspect.Parameter,
    marimo_param: inspect.Parameter,
) -> list[str]:
    name = marimo_param.name
    if group_param.kind is not marimo_param.kind:
        return [
            f"kind mismatch for {name!r}: "
            f"group={group_param.kind.name}, marimo={marimo_param.kind.name}"
        ]
    if group_param.name == "label" or (
        group_method_name == "file_browser" and group_param.name == "on_change"
    ):
        return []
    mismatches: list[str] = []
    if group_param.default != marimo_param.default:
        mismatches.append(
            f"default mismatch for {name!r}: "
            f"group={group_param.default!r}, marimo={marimo_param.default!r}"
        )
    if _annotation_text(group_param) != _annotation_text(marimo_param):
        mismatches.append(
            f"annotation mismatch for {name!r}: "
            f"group={_annotation_text(group_param)!r}, "
            f"marimo={_annotation_text(marimo_param)!r}"
        )
    return mismatches


def _annotation_text(param: inspect.Parameter) -> str:
    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        return ""
    return str(annotation).replace("typing.", "").replace("pathlib.Path", "Path")


def test_help_usage_line_has_no_double_spaces(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.text(label="Name", help_text="A name")
    with pytest.raises(SystemExit):
        g.interface(ctrl)  # no flags, only an option
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "  " not in usage_line


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


def test_dropdown_no_flag_shown_as_mutex_in_usage(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--help"])
    ctrl = g.dropdown(["a", "b"], value="a", label="Style", help_text="The style")
    with pytest.raises(SystemExit):
        g.interface(ctrl)
    usage_line = capsys.readouterr().out.splitlines()[0]
    assert "[--style {a|b} | --no-style]" in usage_line


def test_input_control_freed_when_control_gc_collected() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.slider(start=0, stop=10, value=3, label="Count", help_text="A count")
    input_control = g.interface(ctrl).input_map.get(ctrl)
    assert input_control is not None
    input_control_ref = weakref.ref(input_control)
    del input_control, ctrl
    gc.collect()
    assert input_control_ref() is None


def test_renamed_control_with_same_ui_id_replaces_old_option() -> None:
    g = Group(cli_args=["script.py"])

    old_ctrl = g.switch(label="Be polite", help_text="Enable option")
    ctrl = g.switch(label="Use manners", help_text="Enable option")
    ctrl._id = old_ctrl._id  # type: ignore[reportPrivateUsage]
    input_control = g._input_map.get(ctrl)  # type: ignore[reportPrivateUsage]
    assert input_control is not None
    g._input_map.register(ctrl, input_control)  # type: ignore[reportPrivateUsage]

    assert g.interface(ctrl).missing_options() == []
    assert old_ctrl.value is False


def test_helper_can_make_multiple_label_derived_controls() -> None:
    g = Group(cli_args=["script.py"])

    def make_control(label: str) -> mo.ui.switch:
        # Both controls are created from this same source line; the stale-option
        # cleanup must key off UI identity, not the Python callsite.
        return g.switch(label=label, help_text="Enable option")

    first = make_control("First")
    second = make_control("Second")

    assert g.interface(first, second).missing_options() == []


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


def test_interactive_flag_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["maybe", "y"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    g.interface(ctrl)
    assert ctrl.value is True


def test_interactive_dropdown_none_value_not_treated_as_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropdown with "none" as an allowed value: selecting it by text should not
    be treated as the no-selection sentinel."""
    responses = iter(["none"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.dropdown(
        ["none", "some"],
        value="some",
        label="Mode",
        help_text="Mode",
        allow_select_none=False,
    )
    g.interface(ctrl)
    assert ctrl.value == "none"


def test_parse_query_value_raises_runtime_error_for_broken_control() -> None:
    """A control whose parse() returns None despite the option being present
    should raise RuntimeError, not AssertionError."""

    @dataclasses.dataclass
    class BrokenControl(_options.InputControl):
        def parse(
            self, args: _parse.ParsedArgs
        ) -> _options.ParseResult | _options.ParseError | None:
            return None  # always broken

        def format_help_lines(self) -> list[str]:
            return []

        def format_value(self, value: typing.Any) -> list[str]:
            return []

        def format_query_value(self, value: typing.Any) -> str | None:
            return None

        def format_usage_parts(self) -> list[str]:
            return []

        def create_marimo_element(
            self,
            value: typing.Any,
            label: str,
            *,
            on_change: typing.Any = None,
            disabled: bool = False,
        ) -> typing.Any:
            return None

        def prompt_interactive(self, effective_default: typing.Any = None) -> list[str]:
            return []

        def strategy(self):  # type: ignore[override]
            return None

    ctrl = BrokenControl(option="--foo", help_text="foo", default=None)
    with pytest.raises(RuntimeError, match="bug in the control implementation"):
        ctrl.parse_query_value("bar")


def test_composite_child_keeps_moops_metadata() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.slider(start=0, stop=10, value=3, label="Count", help_text="A count")
    cloned_ctrl = mo.ui.dictionary({"count": ctrl}).elements["count"]
    assert cloned_ctrl is not ctrl
    assert g.interface(cloned_ctrl).missing_options() == []


def test_controls_from_creates_prefixed_dictionary_controls() -> None:
    source = Group(cli_args=["child.py"])
    board = source.text_area(option="--board", value="...", help_text="Board")
    survive = source.multiselect(
        options=["0", "1", "2"],
        value=["1"],
        option="--survive-rule",
        help_text="Survive",
    )
    birth = source.multiselect(
        options=["0", "1", "2"],
        value=["2"],
        option="--birth-rule",
        help_text="Birth",
    )
    child_iface = source.interface(board, survive, birth)

    parent = Group(
        cli_args=[
            "parent.py",
            "--step-board",
            ".#.",
            "--step-survive-rule",
            "2",
            "--step-birth-rule",
            "1",
        ]
    )
    step = parent.controls_from(child_iface, prefix="step")
    parent.interface(step)

    assert list(step.elements) == ["board", "survive_rule", "birth_rule"]
    assert step.value == {
        "board": ".#.",
        "survive_rule": ["2"],
        "birth_rule": ["1"],
    }


def test_controls_from_displays_as_stacked_controls() -> None:
    source = Group(cli_args=["child.py"])
    name = source.text(option="--name", value="Alice", help_text="Name")
    child_iface = source.interface(name)

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")

    mime_type, html = typing.cast(typing.Any, step)._mime_()

    assert mime_type == "text/html"
    assert "display: flex" in html
    assert "marimo-dict" not in html


def test_variant_interfaces_expose_branch_metadata() -> None:
    g = Group(cli_args=["script.py"])
    mode = g.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="Mode",
        allow_select_none=False,
    )
    branches = g.variant("travel", mode)
    distance = branches["car"].number(option="--distance", help_text="Miles")
    car_iface = branches["car"].interface(distance)

    assert car_iface.variant_selector_option == "--mode"
    assert car_iface.variant_selector_parent_prefix == ""
    assert car_iface.variant_key == "car"
    assert car_iface.variant_group_prefix == "travel"


def test_controls_from_variant_displays_only_active_branch() -> None:
    variant_iface = moops.interface_of(variant_trip)
    parent = Group(cli_args=["parent.py"])
    trip = parent.controls_from(variant_iface, prefix="trip")
    visible = typing.cast(typing.Any, trip)

    assert list(trip.elements) == ["mode", "travel-car", "travel-train"]
    assert list(visible._moops_visible_elements()) == ["mode", "travel-car"]

    parent = Group(cli_args=["parent.py", "--trip-mode", "train"])
    trip = parent.controls_from(variant_iface, prefix="trip")
    visible = typing.cast(typing.Any, trip)

    assert list(visible._moops_visible_elements()) == ["mode", "travel-train"]


def test_controls_from_variant_current_args_follow_live_selector_change() -> None:
    """When a mirrored variant selector changes in the notebook, current args
    should serialize the newly active branch, not the branch active at creation.
    """
    variant_iface = moops.interface_of(variant_trip)
    parent = Group(cli_args=["parent.py"])
    trip = parent.controls_from(variant_iface, prefix="trip")
    iface = parent.interface(trip)

    trip.elements["mode"]._value = "train"  # type: ignore[attr-defined]
    trip.elements["mode"]._selected_key = "train"  # type: ignore[attr-defined]
    trip.elements["travel-train"].elements["tickets"]._value = 4  # type: ignore[attr-defined]

    assert iface._current_args() == "--trip-mode train --trip-travel-train-tickets 4"  # type: ignore[attr-defined]


def test_variant_display_uses_selected_key_without_reading_value() -> None:
    class GuardedValueControl:
        _selected_key = "train"
        _moops_input = _options.DropdownControl(
            option="--mode",
            dropdown_opts={"car": "car", "train": "train"},
            supports_none=False,
            default="car",
            help_text="Mode",
        )

        @property
        def value(self) -> typing.NoReturn:
            raise RuntimeError("value should not be read")

    ctrl = GuardedValueControl()
    iface = moops.Interface((ctrl,))
    select = typing.cast(
        typing.Callable[[moops.Interface, str], typing.Any],
        typing.cast(typing.Any, control_mirroring)._selected_value_for_option,
    )

    assert select(iface, "--mode") == "train"


def test_controls_from_supports_overridden_multiselect() -> None:
    source = Group(cli_args=["child.py"])
    survive = source.multiselect(
        options=["0", "1", "2"],
        value=["1"],
        option="--survive-rule",
        help_text="Survive",
    )
    child_iface = source.interface(survive)

    parent = Group.with_overrides({"step": child_iface.default})
    step = parent.controls_from(child_iface, prefix="step")

    assert step.value == child_iface.default


def test_controls_from_excludes_named_controls(
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Group(cli_args=["child.py"])
    board = source.text_area(option="--board", value="...", help_text="Board")
    style = source.dropdown(["a", "b"], option="--style", help_text="Style")
    child_iface = source.interface(board, style)

    parent = Group(cli_args=["parent.py", "--help"])
    child_controls = parent.controls_from(
        child_iface, prefix="child", exclude=["board"]
    )

    with pytest.raises(SystemExit):
        parent.interface(child_controls)

    output = capsys.readouterr().out
    assert "--child-style" in output
    assert "--child-board" not in output


def test_interface_default_correct_for_nested_controls_from() -> None:
    source = Group(cli_args=["child.py"])
    sub = source.subgroup("config")
    style = sub.dropdown(["a", "b"], value="a", option="--style", help_text="Style")
    child_iface = source.interface(sub.interface(style))

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")
    parent_iface = parent.interface(step)

    # default must nest as {"step": {"config": ...}}, not {"step": {"step-config": ...}}
    assert parent_iface.default == {"step": {"config": {"style": "a"}}}


def test_controls_from_value_compatible_with_run_for_child_subgroups() -> None:
    # Child notebook uses a subgroup
    source = Group(cli_args=["child.py"])
    sub = source.subgroup("config")
    style = sub.dropdown(["a", "b"], option="--style", help_text="Style")
    child_iface = source.interface(sub.interface(style))

    # Parent mirrors the child's controls, overriding style to "b"
    parent = Group(cli_args=["parent.py", "--step-config-style", "b"])
    step = parent.controls_from(child_iface, prefix="step")
    parent.interface(step)

    # step.value must be compatible with moops.run(child, **step.value),
    # which passes the dict directly to Group.with_overrides — so nested
    # subgroup values must be dicts, not flat underscore-joined keys.
    assert step.value == {"config": {"style": "b"}}


def test_controls_from_preserves_slider_widget() -> None:
    # controls_from must recreate sliders as sliders, not number inputs.
    source = Group(cli_args=["child.py"])
    count = source.slider(start=0, stop=10, value=3, label="Count", help_text="count")
    child_iface = source.interface(count)

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")
    assert isinstance(step.elements["count"], mo.ui.slider)


def test_controls_from_preserves_extra_kwargs() -> None:
    # controls_from must preserve extra marimo kwargs (e.g. debounce).
    source = Group(cli_args=["child.py"])
    count = source.slider(
        start=0, stop=10, value=3, label="Count", help_text="count", debounce=True
    )
    child_iface = source.interface(count)

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")
    slider = step.elements["count"]
    assert isinstance(slider, mo.ui.slider)
    assert slider._component_args.get("debounce") is True  # type: ignore[attr-defined]


def test_multiselect_empty_selection_is_representable_in_current_args() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.multiselect(
        options=["0", "1", "2", "3"],
        value=["2", "3"],
        option="--survive-rule",
        help_text="Survive rule",
    )
    ctrl._value = []  # type: ignore[attr-defined]

    assert g.interface(ctrl)._current_args() != ""  # type: ignore[attr-defined]


def test_dict_dropdown_on_change_sets_key_not_value_in_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_params: dict[str, str] = {}
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: fake_params)

    def snake_fn(text: str) -> str:
        return "_".join(x.lower() for x in text.split())

    def camel_fn(text: str) -> str:
        return text

    g = Group(cli_args=["script.py"])
    ctrl = g.dropdown(
        {"snake_case": snake_fn, "camel_case": camel_fn},
        value="camel_case",
        label="Style",
        help_text="Text style",
    )

    # marimo passes the dict VALUE to on_change; before the fix this set the
    # query param to str(snake_fn) instead of the key "snake_case".
    on_change = ctrl._on_change  # type: ignore[reportPrivateUsage]
    assert on_change is not None
    on_change(snake_fn)

    assert fake_params.get("style") == "snake_case"


def test_option_named_file_does_not_conflict_with_marimo_notebook_param() -> None:
    class _MockCtrl:
        value = "some_file.txt"

    input_map = _input_map.InputMap()
    ctrl = _MockCtrl()
    input_control = _options.TextControl(
        option="--file", metavar="PATH", default="", help_text="x"
    )
    input_map.register(ctrl, input_control)

    interface = moops.Interface(
        controls=(ctrl,),
        input_map=input_map,
        notebook_file="notebook.py",
    )
    url = interface._standalone_url()  # type: ignore[attr-defined]
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["file"] == "notebook.py"
    assert params.get("file_") == "some_file.txt"


def test_controls_from_values_are_in_standalone_query_values() -> None:
    source = Group(cli_args=["script.py", "--style", "b"])
    ctrl = source.dropdown(["a", "b"], label="Style", help_text="x")
    source_iface = source.interface(ctrl)

    parent = Group(cli_args=["script.py", "--step-style", "b"])
    mirror = parent.controls_from(source_iface, prefix="step")
    iface = parent.interface(mirror)

    assert iface._current_args() == "--step-style b"  # type: ignore[attr-defined]
    assert iface._standalone_query_values() == {  # type: ignore[attr-defined]
        "step_style": "b"
    }


def test_controls_from_current_args_reflects_live_widget_changes() -> None:
    # mo.ui.dictionary clones its elements; the sub-interface must track the
    # live clones (step_controls.elements) not the originals, so that
    # _current_args() picks up user-driven value changes.
    source = Group(cli_args=["child.py"])
    survive = source.multiselect(
        options=[str(i) for i in range(9)],
        value=["2", "3"],
        option="--survive-rule",
        help_text="Survive",
    )
    child_iface = source.interface(survive)

    parent = Group(cli_args=["parent.py"])
    step_controls = parent.controls_from(child_iface, prefix="step")
    parent_iface = parent.interface(step_controls)

    # Simulate user changing the mirrored control's value to a non-default.
    step_controls.elements["survive_rule"]._value = ["1", "2"]  # type: ignore[attr-defined]

    assert "--step-survive-rule" in parent_iface._current_args()  # type: ignore[attr-defined]


def test_nested_controls_from_current_args_reflects_live_widget_changes() -> None:
    source = Group(cli_args=["child.py"])
    config = source.subgroup("config")
    style = config.dropdown(
        ["a", "b"],
        value="a",
        option="--style",
        help_text="Style",
    )
    child_iface = source.interface(config.interface(style))

    parent = Group(cli_args=["parent.py"])
    step_controls = parent.controls_from(child_iface, prefix="step")
    parent_iface = parent.interface(step_controls)

    # Simulate user changing the nested mirrored control's value to a
    # non-default.
    nested_controls = typing.cast(typing.Any, step_controls.elements["config"]).elements
    nested_style = nested_controls["style"]
    nested_style._value = "b"  # type: ignore[attr-defined]
    nested_style._selected_key = "b"  # type: ignore[attr-defined]

    assert parent_iface._current_args() == "--step-config-style b"  # type: ignore[attr-defined]
    assert parent_iface._standalone_query_values() == {  # type: ignore[attr-defined]
        "step_config_style": "b"
    }


def test_custom_control_notebook_element_reuses_component_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = Group(cli_args=["script.py"])
    fallback = g.range_slider(
        start=0,
        stop=10,
        value=[1, 9],
        option="--window",
        help_text="Window",
    )
    empty_params: dict[str, str] = {}
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: empty_params)
    component = mo.ui.range_slider(start=0, stop=10, value=[2, 8])

    def window_value(c: typing.Any, _fb: typing.Any) -> list[int]:
        return list(c.value)

    ctrl = g.custom(fallback, lambda _value: component, value=window_value)

    assert isinstance(ctrl, UIElement)
    assert typing.cast(typing.Any, ctrl)._id == typing.cast(typing.Any, component)._id
    assert typing.cast(typing.Any, ctrl).value == [2, 8]


def test_custom_control_build_uses_fallback_snapshot_without_reading_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct notebook custom controls must not read fallback.value in the cell
    that creates the fallback; marimo guards that access."""
    g = Group(cli_args=["script.py", "--window", "3,7"])
    fallback = g.range_slider(
        start=0,
        stop=10,
        value=[1, 9],
        option="--window",
        help_text="Window",
    )
    input_control = g._input_map.get(fallback)  # type: ignore[reportPrivateUsage]
    assert input_control is not None

    class GuardedFallback:
        _id = fallback._id  # type: ignore[reportPrivateUsage]
        _moops_input = input_control
        _value = fallback._value  # type: ignore[reportPrivateUsage]

        @property
        def value(self) -> typing.NoReturn:
            raise RuntimeError("fallback.value should not be read")

    empty_params: dict[str, str] = {}
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: empty_params)
    built_values: list[typing.Any] = []

    def build(window: typing.Any) -> mo.ui.range_slider:
        built_values.append(window)
        return mo.ui.range_slider(start=0, stop=10, value=list(window))

    ctrl = g.custom(GuardedFallback(), build)

    assert built_values == [[3, 7]]
    assert ctrl.value == [3, 7]


def test_custom_control_recreated_through_controls_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # controls_from must rebuild the notebook component (not just the fallback)
    # when mirroring a child notebook that uses a custom control, and the
    # component's transformed value must flow through the mirror dictionary.
    child = Group(cli_args=["child.py"])
    fallback = child.range_slider(
        start=0, stop=100, value=[10, 20], option="--window", help_text="Window"
    )
    parent = Group(cli_args=["parent.py", "--step-window", "30,40"])

    empty_params: dict[str, str] = {}
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: empty_params)

    def window_value(component: typing.Any, fb: typing.Any) -> dict[str, list[int]]:
        return {"sel": list(component.value), "fb": list(fb.value)}

    window = child.custom(
        fallback,
        lambda x_range: mo.ui.range_slider(start=0, stop=100, value=list(x_range)),
        value=window_value,
    )
    child_iface = child.interface(window)

    step = parent.controls_from(child_iface, prefix="step")
    parent.interface(step)

    mirrored = typing.cast(typing.Any, step).elements["window"]
    assert isinstance(mirrored, CustomElement)
    # value_fn reads the parent's fallback (resolved from --step-window 30,40),
    # not the child's, proving the component was recreated in the parent.
    assert typing.cast(typing.Any, step).value["window"] == {
        "sel": [30, 40],
        "fb": [30, 40],
    }


def test_file_browser_multiple_accepts_repeated_cli_option(
    tmp_path: pathlib.Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first")
    second.write_text("second")

    g = Group(
        cli_args=[
            "script.py",
            "--file",
            str(first),
            "--file",
            str(second),
        ]
    )
    ctrl = g.file_browser(option="--file", help_text="Files to inspect")
    g.interface(ctrl)

    assert [str(info.path) for info in ctrl.value] == [str(first), str(second)]


def test_file_browser_multiple_current_args_repeats_option(
    tmp_path: pathlib.Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second with space.txt"
    first.write_text("first")
    second.write_text("second")

    g = Group(
        cli_args=[
            "script.py",
            "--file",
            str(first),
            "--file",
            str(second),
        ]
    )
    ctrl = g.file_browser(option="--file", help_text="Files to inspect")
    iface = g.interface(ctrl)

    assert iface._current_args() == (  # type: ignore[attr-defined]
        f"--file {first} --file '{second}'"
    )


def test_variant_rejects_inactive_branch_options() -> None:
    g = Group(
        cli_args=[
            "script.py",
            "--mode",
            "car",
            "--travel-train-tickets",
            "5",
        ]
    )
    mode = g.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="How to travel",
        allow_select_none=False,
    )
    travel = g.variant("travel", mode)

    distance = travel["car"].number(
        value=120,
        option="--distance",
        help_text="Driving distance in miles",
    )
    tickets = travel["train"].number(
        value=2,
        option="--tickets",
        help_text="Number of train tickets",
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(
            mode,
            travel["car"].interface(distance),
            travel["train"].interface(tickets),
        )

    assert exc_info.value.code != 0


def test_variant_heading_selected_when_non_default_chosen_without_cli_arg() -> None:
    """Active branch should show (selected), not (default), when the dropdown
    value differs from its default — even with no CLI arg (e.g. changed via UI)."""
    import types

    g = Group(cli_args=["script.py"])  # no --mode arg, simulating notebook mode
    mock_selector = types.SimpleNamespace(
        value="train",
        _moops_input=_options.DropdownControl(
            option="--mode",
            help_text="",
            dropdown_opts={"car": "by car", "train": "by train"},
            supports_none=False,
            default="car",
        ),
    )
    variants = g.variant("travel", mock_selector)
    iface = variants["train"].interface()
    assert iface.help_heading is not None
    assert "(selected)" in iface.help_heading


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


def _number_item(grp: Group) -> typing.Any:
    return grp.number(value=1.0, option="--tag", help_text="Tag")


def _text_item(grp: Group) -> typing.Any:
    return grp.text(value="x", option="--tag", help_text="Tag")


def _dropdown_item(grp: Group) -> typing.Any:
    return grp.dropdown(["a", "b", "c"], value="a", option="--tag", help_text="Tag")


def _multiselect_item(grp: Group) -> typing.Any:
    return grp.multiselect(["a", "b", "c"], value=[], option="--tag", help_text="Tag")


# (label, build_item, values) per supported non-merged list item control.
# The label is only for readable falsifying-example output.
_ItemRoundTripCase = tuple[str, typing.Callable[[Group], typing.Any], list[typing.Any]]

_ROUND_TRIP_ITEM_CASES = typing.cast(
    "st.SearchStrategy[_ItemRoundTripCase]",
    st.one_of(
        st.tuples(
            st.just("number"),
            st.just(_number_item),
            st.lists(st.integers(min_value=0, max_value=100).map(float), max_size=4),
        ),
        st.tuples(
            st.just("text"),
            st.just(_text_item),
            st.lists(st.text(alphabet="abcABC", min_size=1, max_size=4), max_size=4),
        ),
        st.tuples(
            st.just("dropdown"),
            st.just(_dropdown_item),
            st.lists(st.sampled_from(["a", "b", "c", None]), max_size=4),
        ),
        st.tuples(
            st.just("multiselect"),
            st.just(_multiselect_item),
            st.lists(
                st.lists(st.sampled_from(["a", "b", "c"]), unique=True), max_size=4
            ),
        ),
    ),
)


@settings(max_examples=80)
@given(case=_ROUND_TRIP_ITEM_CASES)
def test_list_non_merged_item_round_trips(
    case: _ItemRoundTripCase,
) -> None:
    """A non-merged list should round-trip any item control through CLI args.

    Generalizes over the item control type so the round-trip contract is not
    tied to one control. It covers items that serialize to no per-item token
    (an empty multiselect, whose anchor alone represents the item) and to a
    per-item flag (a dropdown ``None`` rendered as ``--no-tag``): both must
    reparse cleanly rather than being rejected as unexpected arguments.
    """
    _, build_item, values = case

    def build_list(group: Group, value: list[typing.Any]) -> typing.Any:
        return group.list(
            option="--item",
            item=build_item,
            help_text="Items",
            value=value,
        )

    source = Group(cli_args=["script.py"])
    source_ctrl = build_list(source, values)
    current_args = source.interface(source_ctrl)._current_args()  # type: ignore[reportPrivateUsage]
    target = Group(
        cli_args=(
            ["script.py", *shlex.split(current_args)] if current_args else ["script.py"]
        )
    )
    target_ctrl = build_list(target, [])

    target.interface(target_ctrl)

    assert target_ctrl.value == values


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


def test_list_controls_from_variant_parses_nested_items() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--travel-car-distance",
            "100",
            "--trip",
            "--mode",
            "train",
            "--travel-train-tickets",
            "4",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    g.interface(ctrl)

    assert ctrl.value == [
        {
            "mode": "car",
            "travel-car": {"distance": 100, "gas_price": 3.75},
            "travel-train": {"tickets": 2},
        },
        {
            "mode": "train",
            "travel-car": {"distance": 120, "gas_price": 3.75},
            "travel-train": {"tickets": 4},
        },
    ]


def test_list_controls_from_variant_rejects_inactive_branch_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mirrored variant list item should reject options from inactive branches."""
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "train",
            "--travel-car-distance",
            "999",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --travel-car-distance" in capsys.readouterr().out


def test_list_controls_from_current_args_round_trips_default_item() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[variant_iface.default],
    )

    iface = g.interface(ctrl)

    assert iface._current_args() == "--trip"  # type: ignore[attr-defined]


def test_list_controls_from_seeded_items_are_editable() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[
            {
                "mode": "train",
                "travel-car": {"distance": 120, "gas_price": 3.75},
                "travel-train": {"tickets": 4},
            }
        ],
    )

    item = ctrl.elements[0]

    assert item.elements["mode"]._component_args["disabled"] is False  # type: ignore[attr-defined]
    assert (
        item.elements["travel-train"]
        .elements["tickets"]
        ._component_args[  # type: ignore[attr-defined]
            "disabled"
        ]
        is False
    )


def test_list_controls_from_item_edits_update_outer_list_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    changes: list[list[typing.Any]] = []
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[variant_iface.default],
        on_change=changes.append,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]
    item.elements["mode"]._on_change("train")  # type: ignore[attr-defined]
    item.elements["travel-train"].elements["tickets"]._on_change(4)  # type: ignore[attr-defined]

    assert changes[-2][0]["mode"] == "train"
    assert changes[-1][0]["travel-train"]["tickets"] == 4


def test_list_controls_from_variant_displays_only_active_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[
            {
                "mode": "train",
                "travel-car": {"distance": 120, "gas_price": 3.75},
                "travel-train": {"tickets": 4},
            }
        ],
        on_change=lambda _: None,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]

    assert list(item._moops_visible_elements()) == ["mode", "travel-train"]


def test_list_controls_from_rejects_item_option_without_anchor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py", "--mode", "train"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --mode" in capsys.readouterr().out


def test_list_controls_from_allows_following_sibling_options() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--name",
            "Bob",
        ]
    )
    trips = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    iface = g.interface(trips, name)

    assert iface.missing_options() == []
    assert trips.value == [
        {
            "mode": "car",
            "travel-car": {"distance": 120, "gas_price": 3.75},
            "travel-train": {"tickets": 2},
        }
    ]
    assert name.value == "Bob"


def test_list_controls_from_rejects_item_option_after_sibling_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--name",
            "Bob",
            "--travel-train-tickets",
            "4",
        ]
    )
    trips = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    with pytest.raises(SystemExit) as exc_info:
        g.interface(trips, name)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --travel-train-tickets" in capsys.readouterr().out


@settings(max_examples=2)
@given(
    selected=st.sampled_from(["car", "train"]),
    distance=st.integers(min_value=1, max_value=500),
    tickets=st.integers(min_value=1, max_value=20),
)
def test_controls_from_variant_rejects_inactive_branch_args(
    selected: str,
    distance: int,
    tickets: int,
) -> None:
    """Mirrored variants should still reject args for inactive branches."""

    inactive_option = (
        "--trip-travel-train-tickets"
        if selected == "car"
        else "--trip-travel-car-distance"
    )
    active_args = (
        ["--trip-travel-car-distance", str(distance)]
        if selected == "car"
        else ["--trip-travel-train-tickets", str(tickets)]
    )
    inactive_value = str(tickets if selected == "car" else distance)
    g = Group(
        cli_args=[
            "script.py",
            "--trip-mode",
            selected,
            *active_args,
            inactive_option,
            inactive_value,
        ]
    )
    trip = g.controls_from(moops.interface_of(variant_trip), prefix="trip")
    iface = typing.cast(typing.Any, trip)._moops_interface

    assert f"Unexpected argument: {inactive_option}" in list(
        iface.validate(g._state)  # type: ignore[reportPrivateUsage]
    )


def test_list_standalone_query_value_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated standalone query values should hydrate the same list value."""
    source = Group(cli_args=["script.py"])
    source_ctrl = source.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[2.0, 5.0],
    )
    query_values = source.interface(source_ctrl)._standalone_query_values()  # type: ignore[attr-defined]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)

    target = Group(cli_args=["script.py"])
    target_ctrl = target.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    assert target_ctrl.value == [2.0, 5.0]


def test_list_empty_value_overrides_non_empty_default_in_query() -> None:
    """An explicitly empty list is user state, not absence of a query override."""
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[1.0],
    )
    ctrl._value = []  # type: ignore[attr-defined]

    assert g.interface(ctrl)._standalone_query_values() == {  # type: ignore[attr-defined]
        "factor": "[]"
    }


def _control_from(build: typing.Callable[[Group], typing.Any]) -> _options.InputControl:
    """Build a control through the public Group API and return its InputControl.

    Going through the builders (rather than constructing ``_options`` dataclasses
    directly) keeps the generated controls configured exactly as real usage
    produces them -- correct metavars, ``select_opts`` mappings, none handling.
    """
    group = Group(cli_args=["script.py"])
    element = build(group)
    ctrl = group._input_map.get(element)  # type: ignore[reportPrivateUsage]
    assert ctrl is not None
    return ctrl


_DICT_OPTS = {"a": 1, "b": 2, "c": 3}


def _text_ctrl(value: str) -> _options.InputControl:
    return _control_from(lambda g: g.text(value=value, option="--opt", help_text="h"))


def _text_area_ctrl(value: str) -> _options.InputControl:
    return _control_from(
        lambda g: g.text_area(value=value, option="--opt", help_text="h")
    )


def _number_ctrl(value: float | None) -> _options.InputControl:
    return _control_from(lambda g: g.number(value=value, option="--opt", help_text="h"))


def _bounded_number_ctrl(value: float) -> _options.InputControl:
    return _control_from(
        lambda g: g.number(
            start=0, stop=100, value=value, option="--opt", help_text="h"
        )
    )


def _slider_ctrl(value: float) -> _options.InputControl:
    return _control_from(
        lambda g: g.slider(
            start=0, stop=100, value=value, option="--opt", help_text="h"
        )
    )


def _range_ctrl(pair: tuple[float, float]) -> _options.InputControl:
    return _control_from(
        lambda g: g.range_slider(
            start=0, stop=100, value=sorted(pair), option="--opt", help_text="h"
        )
    )


def _dropdown_ctrl(allow_none: bool) -> _options.InputControl:
    return _control_from(
        lambda g: g.dropdown(
            _DICT_OPTS,
            value="a",
            allow_select_none=allow_none,
            option="--opt",
            help_text="h",
        )
    )


def _multiselect_ctrl(default: list[int]) -> _options.InputControl:
    return _control_from(
        lambda g: g.multiselect(
            _DICT_OPTS, value=default, option="--opt", help_text="h"
        )
    )


# A meta strategy over control *types*: each branch yields an InputControl,
# parameterized over the configuration knobs that change its query behavior
# (bounds, none support, default). File controls are intentionally absent: they
# inherit a text ``strategy()`` that generates arbitrary paths, but their
# ``parse_query_value`` rejects paths that do not exist on disk, so their own
# strategy cannot round-trip. Compound list controls have their own round-trip
# tests (``test_list_*_round_trips``).
_QUERY_CONTROL_STRATEGY: st.SearchStrategy[_options.InputControl] = st.one_of(
    st.builds(_text_ctrl, st.text()),
    st.builds(_text_area_ctrl, st.text()),
    st.builds(
        _number_ctrl,
        st.one_of(
            st.none(),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
    ),
    st.builds(_bounded_number_ctrl, st.floats(min_value=0, max_value=100)),
    st.builds(_slider_ctrl, st.floats(min_value=0, max_value=100)),
    st.builds(
        _range_ctrl,
        st.tuples(
            st.floats(min_value=0, max_value=100),
            st.floats(min_value=0, max_value=100),
        ),
    ),
    st.builds(_dropdown_ctrl, st.booleans()),
    st.builds(_multiselect_ctrl, st.lists(st.sampled_from([1, 2, 3]), unique=True)),
)


@st.composite
def _control_and_value(
    draw: st.DrawFn,
) -> tuple[_options.InputControl, typing.Any]:
    """Draw a control type, then a value from that control's own ``strategy()``."""
    control = draw(_QUERY_CONTROL_STRATEGY)
    return control, draw(control.strategy())


@pytest.mark.filterwarnings("ignore:.*outside the range of safe integers")
@settings(max_examples=300)
@given(case=_control_and_value())
def test_all_control_types_query_param_round_trip(
    case: tuple[_options.InputControl, typing.Any],
) -> None:
    """Any value round-trips through a control's query-param serialization.

    Generalizes the per-control round-trip checks over the control type itself:
    ``format_query_value`` then ``parse_query_value`` must reconstruct the value,
    and a ``None`` (omitted) serialization must mean the value equals the default
    (so loading without the param hydrates the same value).
    """
    control, value = case
    formatted = control.format_query_value(value)
    if formatted is None:
        assert value == control.default
        return
    result = control.parse_query_value(formatted)
    assert isinstance(result, _options.ParseResult), result
    assert result.value == value


@pytest.mark.filterwarnings("ignore:.*outside the range of safe integers")
@settings(max_examples=300)
@given(case=_control_and_value())
def test_all_control_types_cli_round_trip(
    case: tuple[_options.InputControl, typing.Any],
) -> None:
    """Any value round-trips through a control's CLI serialization.

    The companion to the query-param round-trip, over the same meta strategy:
    ``format_value`` then reparsing the resulting tokens must reconstruct the
    value, and an empty serialization must mean the value equals the default.
    Subsumes the per-control CLI parse checks (e.g. negative numbers).
    """
    control, value = case
    tokens = shlex.split(" ".join(control.format_value(value)))
    if not tokens:
        assert value == control.default
        return
    result = control.parse(_parse.ParsedArgs.from_options(tokens))
    assert isinstance(result, _options.ParseResult), result
    assert result.value == value


def test_list_merged_dropdown_item_accepts_no_flag() -> None:
    """Merged lists must parse the item control's auxiliary flags too.

    A dropdown item with a non-None default formats a None item as --no-style;
    the same argument should be accepted when pasted back into the CLI.
    """
    source = Group(cli_args=["script.py"])
    source_ctrl = source.list(
        option="--style",
        item=lambda grp: grp.dropdown(
            ["a", "b"], value="a", option="--style", help_text="Style"
        ),
        help_text="Styles",
        value=[None],
    )
    args = source.interface(source_ctrl)._current_args()  # type: ignore[attr-defined]

    target = Group(cli_args=["script.py", *args.split()])
    target_ctrl = target.list(
        option="--style",
        item=lambda grp: grp.dropdown(
            ["a", "b"], value="a", option="--style", help_text="Style"
        ),
        help_text="Styles",
        value=[],
    )

    target.interface(target_ctrl)

    assert target_ctrl.value == [None]


def test_interactive_list_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, list controls should prompt for items.

    The current prompt_interactive() stub returns {} unconditionally, so the
    list stays empty instead of collecting the user's inputs."""
    responses = iter(["2", "5", ""])  # two items, empty to stop

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    g.interface(ctrl)
    assert ctrl.value == [2.0, 5.0]


def test_interactive_list_non_merged_anchor_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, non-merged list controls should prompt for items."""
    responses = iter(["2", "5", ""])  # two items, empty to stop

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    g.interface(ctrl)
    assert ctrl.value == [2.0, 5.0]


def test_interactive_list_controls_from_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, subgroup list controls should prompt for items."""
    child = Group(cli_args=["child.py"])
    name = child.text(value="", option="--name", help_text="Name")
    age = child.number(value=0, option="--age", help_text="Age")
    child_iface = child.interface(name, age)
    responses = iter(["Alice", "30", ""])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--person",
        item=lambda grp: grp.controls_from(child_iface, prefix="person"),
        help_text="People",
        value=[],
    )

    g.interface(ctrl)

    assert ctrl.value == [{"name": "Alice", "age": 30}]
