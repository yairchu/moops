import asyncio
import dataclasses
import gc
import inspect
import pathlib
import typing
import urllib.parse
import weakref

import marimo as mo
import pytest
from marimo._plugins.ui._core.ui_element import UIElement

import moops
import moops.group as group_module
from moops import Group, _input_map, _options, _parse


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

    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "md", fake_md)

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


def test_number_accepts_negative_value() -> None:
    g = Group(cli_args=["script.py", "--count", "-3"])
    ctrl = g.number(option="--count", help_text="A count")
    g.interface(ctrl)
    assert ctrl.value == -3


def test_group_ui_method_positional_args_match_marimo() -> None:
    group_names = {
        name for name, _ in inspect.getmembers(Group, predicate=inspect.isfunction)
    }
    marimo_names = {name for name in dir(mo.ui) if not name.startswith("_")}
    shared = group_names & marimo_names

    mismatches = {
        name: mismatch
        for name in shared
        for mismatch in [
            _positional_signature_mismatch(getattr(Group, name), getattr(mo.ui, name))
        ]
        if mismatch is not None
    }

    assert not mismatches, "\n".join(
        [
            "Group UI method positional signature mismatches:\n",
            *[f"{name}: {mismatch}" for name, mismatch in mismatches.items()],
        ]
    )


def _positional_signature_mismatch(
    group_func: typing.Callable[..., typing.Any],
    marimo_func: typing.Callable[..., typing.Any],
) -> str | None:
    [*group_params] = inspect.signature(group_func).parameters.values()
    if group_params and group_params[0].name == "self":
        group_params = group_params[1:]

    positional = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )

    for index, mo_param in enumerate(
        inspect.signature(marimo_func).parameters.values()
    ):
        if mo_param.kind not in positional or mo_param.name == "disabled":
            break
        if index >= len(group_params):
            return f"missing param {mo_param.name!r} at index {index}"
        g_param = group_params[index]
        if g_param.kind is inspect.Parameter.VAR_POSITIONAL:
            return None
        if g_param.kind not in positional or g_param.name != mo_param.name:
            return (
                f"index {index}: expected positional {mo_param.name!r}, "
                f"got {g_param.kind.name} {g_param.name!r}"
            )
        if (
            mo_param.default is not inspect.Parameter.empty
            and g_param.default != mo_param.default
        ):
            return (
                f"default mismatch for {mo_param.name!r}: "
                f"group={g_param.default!r}, marimo={mo_param.default!r}"
            )
    return None


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

        def prompt_interactive(
            self, effective_default: typing.Any = None
        ) -> dict[str, str | None]:
            return {}

        def strategy(self):  # type: ignore[override]
            return None

    ctrl = BrokenControl(option="--foo", help_text="foo")
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
