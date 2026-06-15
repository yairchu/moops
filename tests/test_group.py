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
from marimo._plugins.ui._core.ui_element import UIElement

import moops
import moops.group as group_module
import moops.interface as interface_module
from moops import Group, _input_map, _options, _parse
from moops._ui_workarounds import FileBrowserWithInitialSelection


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


def test_overridden_dropdown_accepts_non_string_option_value() -> None:
    class Adam:
        pass

    class SGD:
        pass

    g = Group(cli_args=["script.py"])
    optimizer = g.subgroup("optimizer", overrides={"kind": Adam})
    ctrl = optimizer.dropdown(
        {"Adam": Adam, "SGD": SGD},
        option="--kind",
        help_text="Optimizer",
        allow_select_none=False,
    )

    assert ctrl.value is Adam
    assert ctrl._selected_key == "Adam"  # type: ignore[attr-defined]


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


def test_number_accepts_split_negative_decimal_without_leading_zero() -> None:
    g = Group(cli_args=["script.py", "--count", "-.5"])
    ctrl = g.number(option="--count", help_text="A count")
    assert ctrl.value == -0.5


def test_range_slider_accepts_split_negative_start() -> None:
    g = Group(cli_args=["script.py", "--range", "-5,10"])
    ctrl = g.range_slider(
        start=-100,
        stop=100,
        value=[0, 10],
        option="--range",
        help_text="Range",
    )
    assert ctrl.value == [-5.0, 10.0]


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

    # Some Group methods intentionally deviate from marimo signatures;
    # table only supports a specific subset of marimo's input types.
    signature_whitelist = {"table"}

    mismatches = {
        name: mismatches
        for name in shared
        if name not in signature_whitelist
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
        if g_param.kind in [
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ]:
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


def test_interactive_multiselect_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["a,typo", "a,c"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["a", "c"]


def test_interactive_multiselect_accepts_numbered_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["1,3"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["a", "c"]


def test_interactive_multiselect_eof_after_invalid_input_keeps_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["typo"])

    def fake_input(_prompt: str) -> str:
        try:
            return next(responses)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["b"]


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

    assert car_iface.variant_ctx.selector_option == "--mode"
    assert car_iface.variant_ctx.selector_parent_prefix == ""
    assert car_iface.variant_ctx.key == "car"
    assert car_iface.variant_ctx.group_prefix == "travel"


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
    assert interface_module.selected_value_for_option(iface, "--mode") == "train"


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


def test_file_browser_fallback_display_preserves_default_paths() -> None:
    ctrl = FileBrowserWithInitialSelection(
        default=["second.txt", "first.txt", "second.txt"],
        initial_path="",
        label="Files",
        multiple=True,
    )

    mime_type, rendered = ctrl._mime_()  # type: ignore[reportPrivateUsage]

    assert mime_type == "text/html"
    assert rendered.index("second.txt") < rendered.index("first.txt")
    assert rendered.count("second.txt") == 2


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
    assert iface.variant_ctx.help_heading is not None
    assert "(selected)" in iface.variant_ctx.help_heading
