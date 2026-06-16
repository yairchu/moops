import typing

import marimo as mo
import pytest
from marimo._plugins.ui._core.ui_element import UIElement

import moops
import moops.group as group_module
from examples.composition import variant_trip
from moops import Group
from moops._custom_element import CustomElement


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


def test_controls_from_text_embeds_stacked_controls() -> None:
    # Composite controls embed child UI elements through their .text HTML, not
    # through _mime_(). Mirrored controls must keep the stacked display there too.
    source = Group(cli_args=["child.py"])
    name = source.text(option="--name", value="Alice", help_text="Name")
    child_iface = source.interface(name)

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")

    assert "display: flex" in step.text
    assert "marimo-dict" not in step.text


def test_controls_from_result_is_reactive_ui_element() -> None:
    # controls_from's result must be a UIElement: marimo only reruns cells that
    # reference it when the bound global is a UIElement (UIElementRegistry scans
    # the namespace for `isinstance(value, UIElement)`). A non-UIElement wrapper
    # leaves the dictionary bound to no global, so editing a mirrored control
    # never propagates until some other element forces a rerun.
    source = Group(cli_args=["child.py"])
    name = source.text(option="--name", value="Alice", help_text="Name")
    child_iface = source.interface(name)

    parent = Group(cli_args=["parent.py"])
    step = parent.controls_from(child_iface, prefix="step")

    # The child clones are lens views of the dictionary, so their updates
    # resolve up to it — which propagates only if the dictionary itself is the
    # UIElement bound to the global.
    assert isinstance(step, UIElement)


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


def test_controls_from_variant_supports_switch_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A switch/checkbox is a valid variant selector (_variant.keys accepts
    # FlagControl), but in the controls_from mirroring path the selector is a
    # freshly-cloned widget, so finding the active branch by reading its
    # `.value` trips marimo's "value accessed in its creating cell" guard --
    # dropdowns dodge it via `_selected_key`, switches have none. Regression:
    # selected_key must read the raw `_value`, so switch-driven variants render
    # (e.g. in pipeline step controls), not raise.
    source = Group(cli_args=["child.py"])
    enable = source.switch(value=False, flag="--enable", help_text="Enable")
    branches = source.variant("opt", enable)
    count = branches[True].number(value=1, option="--count", help_text="Count")
    child_iface = source.interface(enable, branches[True].interface(count))

    parent = Group(cli_args=["parent.py"])
    mirror = parent.controls_from(child_iface, prefix="step")
    visible = typing.cast(typing.Any, mirror)

    # Simulate marimo's creating-cell guard: reading any widget's `.value`
    # raises. The fix must resolve the selector without touching `.value`.
    def guarded_value(self: typing.Any) -> typing.Any:
        raise RuntimeError(
            "Accessing the value of a UIElement in the cell that created it"
        )

    monkeypatch.setattr(UIElement, "value", property(guarded_value))

    # Selector is off (default False), so the True-branch controls stay hidden;
    # the call must succeed rather than raise on the switch's guarded `.value`.
    assert list(visible._moops_visible_elements()) == ["enable"]


def test_controls_from_nested_variant_displays_only_active_branch() -> None:
    source = Group(cli_args=["child.py"])
    mode = source.dropdown(
        ["advanced", "simple"],
        value="advanced",
        option="--mode",
        help_text="Mode",
        allow_select_none=False,
    )
    mode_branches = source.variant("mode", mode)

    advanced = mode_branches["advanced"]
    detail = advanced.dropdown(
        ["basic", "custom"],
        value="basic",
        option="--detail",
        help_text="Detail level",
        allow_select_none=False,
    )
    detail_branches = advanced.variant("detail", detail)
    basic_count = detail_branches["basic"].number(
        value=1,
        option="--count",
        help_text="Count",
    )
    custom_name = detail_branches["custom"].text(
        value="example",
        option="--name",
        help_text="Name",
    )
    simple_count = mode_branches["simple"].number(
        value=2,
        option="--count",
        help_text="Count",
    )
    child_iface = source.interface(
        mode,
        advanced.interface(
            detail,
            detail_branches["basic"].interface(basic_count),
            detail_branches["custom"].interface(custom_name),
        ),
        mode_branches["simple"].interface(simple_count),
    )

    parent = Group(cli_args=["parent.py"])
    mirror = parent.controls_from(child_iface, prefix="settings")
    visible = typing.cast(typing.Any, mirror)
    advanced_mirror = typing.cast(typing.Any, mirror.elements["mode-advanced"])

    assert list(visible._moops_visible_elements()) == ["mode", "mode-advanced"]
    # The active outer variant branch is itself a mirrored subgroup containing
    # another variant. It should keep the same variant-aware display API as the
    # top-level mirror, so the inactive nested branch can be hidden.
    assert list(advanced_mirror._moops_visible_elements()) == [
        "detail",
        "detail-basic",
    ]


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


def test_controls_from_preserves_explicit_label() -> None:
    # A control whose explicit label differs from its option name (a short
    # option carrying a fuller label) must keep that label when mirrored via
    # controls_from. Otherwise the mirror derives the displayed label from the
    # option name, so a mirrored "--count" shows "count" instead of its real
    # "Maximum item count" label.
    source = Group(cli_args=["child.py"])
    count = source.slider(
        start=0,
        stop=10,
        value=3,
        label="Maximum item count",
        option="--count",
        help_text="how many items",
    )
    child_iface = source.interface(count)

    parent = Group(cli_args=["parent.py"])
    mirror = parent.controls_from(child_iface, prefix="step")

    mirrored = mirror.elements["count"]
    assert "Maximum item count" in typing.cast(typing.Any, mirrored).text


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


def test_controls_from_standalone_query_values_hydrate_mirror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Group(cli_args=["child.py"])
    ctrl = source.dropdown(
        ["a", "b"],
        value="a",
        option="--style",
        help_text="Style",
        allow_select_none=False,
    )
    child_iface = source.interface(ctrl)

    parent = Group(cli_args=["parent.py", "--step-style", "b"])
    mirror = parent.controls_from(child_iface, prefix="step")
    query_values = parent.interface(mirror)._standalone_query_values()  # type: ignore[attr-defined]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)

    target = Group(cli_args=["parent.py"])
    target_mirror = target.controls_from(child_iface, prefix="step")

    assert target_mirror.value == {"style": "b"}


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
