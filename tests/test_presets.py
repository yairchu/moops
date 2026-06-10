import pathlib
import typing
from unittest import mock

import pytest

from moops import Group, _text_wrap
from moops.interface import Interface
from moops.presets import Presets


def _mock_presets(**attrs: typing.Any) -> Presets:
    """Build a ``Presets`` test double with safe defaults.

    Uses ``spec=Presets`` so typos or removed methods raise ``AttributeError``
    instead of silently returning a truthy child ``Mock``. In particular
    ``get_pending_cli`` defaults to ``None``: a stray ``Mock`` there flows into
    ``mo.ui.text_area(value=...)`` and sends marimo into unbounded allocation
    (a multi-GB hang), so callers must opt in to a real value.
    """
    defaults: dict[str, typing.Any] = {"get_pending_cli": mock.Mock(return_value=None)}
    return typing.cast(Presets, mock.Mock(spec=Presets, **{**defaults, **attrs}))


def _mock_preset_caller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    filename: str = "notebook.py",
) -> None:
    monkeypatch.setattr("moops.presets._stack_filename", lambda: tmp_path / filename)


def test_preset_ui_elements_stable_across_renders(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_preset_caller(monkeypatch, tmp_path)
    presets = Presets(lambda: None, lambda _: None)
    iface = Interface(controls=(), presets=presets, command="script.py")
    assert iface._presets_ui is not None  # type: ignore[reportPrivateUsage]
    iface._mime_()  # type: ignore[misc]
    first = iface._presets_ui  # type: ignore[reportPrivateUsage]
    iface._mime_()  # type: ignore[misc]
    assert iface._presets_ui is first  # type: ignore[reportPrivateUsage]


def test_selected_preset_updates_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Url", "style": "camel"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    presets = _mock_presets(selected_args="--text Preset --style snake")
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Default", option="--text", help_text="Input text")
    style = group.dropdown(
        ["snake", "camel"],
        value="camel",
        option="--style",
        help_text="Text style",
        allow_select_none=False,
    )

    assert text.value == "Preset"
    assert style.value == "snake"
    assert params == {"text": "Preset", "style": "snake"}


def test_selected_preset_clears_unspecified_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Url", "style": "camel"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    presets = _mock_presets(selected_args="--style snake")
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Default", option="--text", help_text="Input text")
    style = group.dropdown(
        ["snake", "camel"],
        value="camel",
        option="--style",
        help_text="Text style",
        allow_select_none=False,
    )

    assert text.value == "Default"
    assert style.value == "snake"
    assert params == {"style": "snake"}


def test_query_params_disable_default_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Url"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    presets = _mock_presets(
        selected_args="",
        default_args="--text DefaultPreset --style snake",
        get_current=mock.Mock(return_value=None),
    )
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Default", option="--text", help_text="Input text")
    style = group.dropdown(
        ["snake", "camel"],
        value="camel",
        option="--style",
        help_text="Text style",
        allow_select_none=False,
    )

    assert text.value == "Url"
    assert style.value == "camel"
    assert params == {"text": "Url"}


def test_default_preset_is_selected_in_dropdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    def _args_for(name: str | None) -> str:
        return "--text DefaultPreset" if name == "default" else ""

    presets = _mock_presets(
        selected_args="",
        default_args="--text DefaultPreset",
        get_current=mock.Mock(return_value=None),
        args_for=mock.Mock(side_effect=_args_for),
        list=mock.Mock(return_value=["default"]),
    )
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Default", option="--text", help_text="Input text")
    iface = group.interface(text)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    assert presets_ui._dropdown.value == "default"


def test_factory_preset_selection_clears_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Preset", "style": "snake"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    select = mock.Mock()
    presets = _mock_presets(
        selected_args="--text Preset --style snake",
        default_args="--text DefaultPreset",
        get_current=mock.Mock(return_value="saved"),
        args_for=mock.Mock(return_value="--text Preset --style snake"),
        list=mock.Mock(return_value=["default", "saved"]),
        select=select,
    )
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Factory", option="--text", help_text="Input text")
    style = group.dropdown(
        ["snake", "camel"],
        value="camel",
        option="--style",
        help_text="Text style",
        allow_select_none=False,
    )
    iface = group.interface(text, style)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    presets_ui._dropdown._on_change(None)

    select.assert_called_once_with("")
    assert params == {}


def test_reset_button_reapplies_active_factory_preset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Edited"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    select = mock.Mock()
    presets = _mock_presets(
        selected_args="",
        default_args="",
        get_current=mock.Mock(return_value=""),
        args_for=mock.Mock(return_value=""),
        list=mock.Mock(return_value=["default", "saved"]),
        select=select,
    )
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Factory", option="--text", help_text="Input text")
    iface = group.interface(text)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    presets_ui._reset_btn._on_click(None)

    select.assert_called_once_with("")
    assert params == {}


def test_reset_button_clears_list_notebook_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"factor": "[1.0]"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    select = mock.Mock()
    changes: list[list[float]] = []
    presets = _mock_presets(
        selected_args="",
        default_args="",
        get_current=mock.Mock(return_value=None),
        args_for=mock.Mock(return_value=""),
        list=mock.Mock(return_value=["saved"]),
        select=select,
    )
    group = Group(cli_args=["script.py"], presets=presets)
    factors = group.list(
        option="--factor",
        item=lambda g: g.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[1.0],
        on_change=changes.append,
    )
    iface = group.interface(factors)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    presets_ui._reset_btn._on_click(None)

    select.assert_called_once_with("")
    assert params == {}
    assert changes == [[]]


def test_reset_button_reapplies_inherited_preset_to_subgroup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"child.text": "Edited"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    select = mock.Mock()
    changes: list[str] = []
    presets = _mock_presets(
        selected_args="",
        default_args="",
        get_current=mock.Mock(return_value="saved"),
        args_for=mock.Mock(return_value="--child-text Preset"),
        list=mock.Mock(return_value=["saved"]),
        select=select,
    )
    group = Group(cli_args=["script.py"], presets=presets)
    child = group.subgroup("child")
    text = child.text(
        value="Factory",
        option="--text",
        help_text="Input text",
        on_change=changes.append,
    )
    child_iface = child.interface(text)
    iface = group.interface(child_iface)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    presets_ui._reset_btn._on_click(None)

    select.assert_called_once_with("saved")
    assert params == {"child.text": "Preset"}
    assert changes == ["Preset"]


def test_selected_default_preset_does_not_override_edited_list_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"factor": "[2.0, 1.0]"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    presets = _mock_presets(
        selected_args="--factor 2",
        default_args="--factor 2",
        get_current=mock.Mock(return_value="default"),
    )
    group = Group(cli_args=["script.py"], presets=presets)
    factors = group.list(
        option="--factor",
        item=lambda g: g.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[2.0, 1.0],
        on_change=lambda _: None,
    )

    assert factors.value == [2.0, 1.0]
    assert params == {"factor": "[2.0, 1.0]"}


def test_selected_default_preset_does_not_lock_edited_subgroup_list_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    preset_trip = [{"mode": "car", "distance": 120}]
    edited_trip = [*preset_trip, {"mode": "car", "distance": 120}]
    presets = _mock_presets(
        selected_args="--trip --mode car --distance 120",
        default_args="--trip --mode car --distance 120",
        get_current=mock.Mock(return_value="default"),
    )
    template = Group(cli_args=["template.py"])
    mode = template.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="Travel mode",
        allow_select_none=False,
    )
    distance = template.number(
        value=120,
        option="--distance",
        help_text="Distance",
    )
    template_iface = template.interface(mode, distance)

    group = Group(cli_args=["script.py"], presets=presets)
    changes: list[list[dict[str, typing.Any]]] = []
    trips = group.list(
        option="--trip",
        item=lambda g: g.controls_from(template_iface, prefix="trip"),
        help_text="Trips",
        value=preset_trip,
        on_change=changes.append,
    )
    trips._add_btn._on_click(None)

    assert changes == [edited_trip]
    assert params == {
        "trip": ('[{"mode": "car", "distance": 120}, {"mode": "car", "distance": 120}]')
    }

    rerendered_group = Group(cli_args=["script.py"], presets=presets)
    rerendered_trips = rerendered_group.list(
        option="--trip",
        item=lambda g: g.controls_from(template_iface, prefix="trip"),
        help_text="Trips",
        value=changes[-1],
        on_change=lambda _: None,
    )

    assert rerendered_trips.value == edited_trip


def test_empty_save_name_saves_default_preset() -> None:
    save = mock.Mock()
    presets = _mock_presets(
        get_current=mock.Mock(return_value=None),
        args_for=mock.Mock(return_value=""),
        list=mock.Mock(return_value=[]),
        save=save,
    )
    group = Group(cli_args=["script.py", "--text", "Edited"])
    text = group.text(value="Factory", option="--text", help_text="Input text")
    iface = Interface(
        controls=(text,),
        input_map=group._input_map,  # type: ignore[reportPrivateUsage]
        presets=presets,
        command="script.py",
    )
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout("--text Edited")

    presets_ui._save_btn._on_click(None)

    save.assert_called_once_with("default", "--text Edited")


def test_default_preset_rename_placeholder_is_not_default() -> None:
    presets = _mock_presets(
        args_for=mock.Mock(return_value="--text DefaultPreset"),
        get_current=mock.Mock(return_value="default"),
        list=mock.Mock(return_value=["default"]),
    )
    iface = Interface(
        controls=(),
        presets=presets,
        active_preset="default",
        command="script.py",
    )
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout("--text DefaultPreset")

    assert presets_ui._rename_input._component_args["placeholder"] == "preset name"


def test_factory_preset_can_reset_saved_default() -> None:
    delete = mock.Mock()
    presets = _mock_presets(
        args_for=mock.Mock(return_value=""),
        default_args="--text DefaultPreset",
        get_current=mock.Mock(return_value=""),
        list=mock.Mock(return_value=["default"]),
        delete=delete,
    )
    iface = Interface(
        controls=(),
        presets=presets,
        active_preset=None,
        command="script.py",
    )
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout("")

    presets_ui._reset_default_btn._on_click(None)

    delete.assert_called_once_with("default")


def test_command_box_wraps_long_command_like_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The editable command box should use the same line-split formatting the
    read-only markdown code block does.

    Known failure: ``command_box`` currently shows the flat single-line command
    (``f"{name} {args}"``), while the no-presets markdown fallback wraps long
    commands with ``\\``-continuations via ``wrap_command``.
    """
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    long_value = "a-value-long-enough-to-push-this-command-past-the-wrap-width"
    presets = _mock_presets(
        selected_args="",
        default_args="",
        get_current=mock.Mock(return_value=None),
        args_for=mock.Mock(return_value=""),
        list=mock.Mock(return_value=[]),
    )
    group = Group(cli_args=["script.py", "--text", long_value], presets=presets)
    text = group.text(value="Default", option="--text", help_text="Input text")
    iface = group.interface(text)

    expected = _text_wrap.wrap_command("script.py", iface._arg_groups())  # type: ignore[reportPrivateUsage]
    assert "\n" in expected  # sanity: this command is long enough to wrap

    iface._mime_()  # type: ignore[misc]
    box_value = typing.cast(typing.Any, iface)._presets_ui._command_input.value

    assert box_value == expected


def test_command_box_accepts_args_for_variant_selected_by_edit() -> None:
    g = Group(cli_args=["script.py"])
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
        help_text="Driving distance",
    )
    tickets = travel["train"].number(
        value=2,
        option="--tickets",
        help_text="Number of train tickets",
    )
    iface = g.interface(
        mode,
        travel["car"].interface(distance),
        travel["train"].interface(tickets),
    )

    errors = iface.apply_cli_args("script.py --mode train --travel-train-tickets 5")

    assert errors == ()


def test_delete_calls_select_to_trigger_rerender(
    tmp_path: pathlib.Path,
) -> None:
    selected: list[typing.Any] = []
    filename = tmp_path / "presets.json"
    presets = Presets(
        get_selected_preset=lambda: None,
        set_selected_preset=selected.append,
        filename=filename,
    )
    presets.save("default", "--foo bar")
    selected.clear()

    presets.delete("default")

    assert [s.preset for s in selected] == [""]
    assert filename.exists()


def test_presets_can_infer_filename_from_caller(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_preset_caller(monkeypatch, tmp_path)
    selected: list[typing.Any] = []
    presets = Presets(lambda: None, selected.append)

    presets.save("default", "--foo bar")

    assert (tmp_path / "notebook_presets.json").read_text() == (
        '{\n  "presets": {\n    "default": "--foo bar"\n  }\n}'
    )
    assert [s.preset for s in selected] == ["default"]


def test_presets_prefer_marimo_notebook_filename(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notebook = tmp_path / "notebook.py"
    generated_cell = tmp_path / "marimo_123" / "__marimo__cell_Xref__presets.py"
    monkeypatch.setattr("moops.presets._stack_filename", lambda: generated_cell)
    monkeypatch.setattr("moops.presets._marimo_notebook_filename", lambda: notebook)

    presets = Presets(lambda: None, lambda _: None)
    presets.save("default", "--foo bar")

    assert (tmp_path / "notebook_presets.json").exists()
    assert not (generated_cell.parent / "__marimo__cell_Xref__presets.json").exists()


def test_interactive_enter_uses_default_preset_value(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_input(_prompt: str) -> str:
        return ""  # press Enter

    monkeypatch.setattr("builtins.input", fake_input)
    _mock_preset_caller(monkeypatch, tmp_path)
    presets = Presets(lambda: None, lambda _: None)
    presets.save("default", "--verbose")

    g = Group(cli_args=["script.py", "--interactive"], presets=presets)
    ctrl = g.switch(value=False, flag="--verbose", help_text="Enable verbose output")
    g.interface(ctrl)

    assert ctrl.value is True  # preset value, not hardcoded False
