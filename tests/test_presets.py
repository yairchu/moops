import pathlib
import typing
from unittest import mock

import pytest

from moops import Group
from moops.interface import Interface
from moops.presets import Presets


def _mock_preset_caller(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    filename: str = "notebook.py",
) -> None:
    caller = mock.Mock(filename=str(tmp_path / filename))
    frame = mock.Mock(filename=str(tmp_path / "test.py"))
    monkeypatch.setattr("moops.presets.inspect.stack", lambda: [frame, frame, caller])


def test_preset_ui_elements_stable_across_renders(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_preset_caller(monkeypatch, tmp_path)
    presets = Presets(lambda: None, lambda _: None)
    iface = Interface(controls=(), presets=presets, command="script.py")  # type: ignore[arg-type]
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

    presets = typing.cast(
        Presets,
        mock.Mock(selected_args="--text Preset --style snake"),
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

    assert text.value == "Preset"
    assert style.value == "snake"
    assert params == {"text": "Preset", "style": "snake"}


def test_selected_preset_clears_unspecified_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params = {"text": "Url", "style": "camel"}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)

    presets = typing.cast(Presets, mock.Mock(selected_args="--style snake"))
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

    presets = typing.cast(
        Presets,
        mock.Mock(
            selected_args="",
            default_args="--text DefaultPreset --style snake",
            get_current=mock.Mock(return_value=None),
        ),
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

    presets = typing.cast(
        Presets,
        mock.Mock(
            selected_args="",
            default_args="--text DefaultPreset",
            get_current=mock.Mock(return_value=None),
            args_for=mock.Mock(side_effect=_args_for),
            list=mock.Mock(return_value=["default"]),
        ),
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
    presets = typing.cast(
        Presets,
        mock.Mock(
            selected_args="--text Preset --style snake",
            default_args="--text DefaultPreset",
            get_current=mock.Mock(return_value="saved"),
            args_for=mock.Mock(return_value="--text Preset --style snake"),
            list=mock.Mock(return_value=["default", "saved"]),
            select=select,
        ),
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
    presets = typing.cast(
        Presets,
        mock.Mock(
            selected_args="",
            default_args="",
            get_current=mock.Mock(return_value=""),
            args_for=mock.Mock(return_value=""),
            list=mock.Mock(return_value=["default", "saved"]),
            select=select,
        ),
    )
    group = Group(cli_args=["script.py"], presets=presets)
    text = group.text(value="Factory", option="--text", help_text="Input text")
    iface = group.interface(text)
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout(iface._current_args())  # type: ignore[reportPrivateUsage]

    presets_ui._reset_btn._on_click(None)

    select.assert_called_once_with("")
    assert params == {}


def test_empty_save_name_saves_default_preset() -> None:
    save = mock.Mock()
    presets = typing.cast(
        Presets,
        mock.Mock(
            get_current=mock.Mock(return_value=None),
            args_for=mock.Mock(return_value=""),
            list=mock.Mock(return_value=[]),
            save=save,
        ),
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
    presets = typing.cast(
        Presets,
        mock.Mock(
            args_for=mock.Mock(return_value="--text DefaultPreset"),
            get_current=mock.Mock(return_value="default"),
            list=mock.Mock(return_value=["default"]),
        ),
    )
    iface = Interface(
        controls=typing.cast(tuple[typing.Any], ()),
        presets=presets,
        active_preset="default",
        command="script.py",
    )
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout("--text DefaultPreset")

    assert presets_ui._rename_input._component_args["placeholder"] == "preset name"


def test_factory_preset_can_reset_saved_default() -> None:
    delete = mock.Mock()
    presets = typing.cast(
        Presets,
        mock.Mock(
            args_for=mock.Mock(return_value=""),
            default_args="--text DefaultPreset",
            get_current=mock.Mock(return_value=""),
            list=mock.Mock(return_value=["default"]),
            delete=delete,
        ),
    )
    iface = Interface(
        controls=typing.cast(tuple[typing.Any], ()),
        presets=presets,
        active_preset=None,
        command="script.py",
    )
    presets_ui = typing.cast(typing.Any, iface)._presets_ui
    presets_ui.layout("")

    presets_ui._reset_default_btn._on_click(None)

    delete.assert_called_once_with("default")


def test_delete_calls_select_to_trigger_rerender(
    tmp_path: pathlib.Path,
) -> None:
    selected: list[str | None] = []
    filename = tmp_path / "presets.json"
    presets = Presets(
        get_selected_preset=lambda: None,
        set_selected_preset=selected.append,
        filename=filename,
    )
    presets.save("default", "--foo bar")
    selected.clear()

    presets.delete("default")

    assert selected == [""]
    assert filename.exists()


def test_presets_can_infer_filename_from_caller(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_preset_caller(monkeypatch, tmp_path)
    selected: list[str | None] = []
    presets = Presets(lambda: None, selected.append)

    presets.save("default", "--foo bar")

    assert (tmp_path / "notebook_presets.json").read_text() == (
        '{\n  "presets": {\n    "default": "--foo bar"\n  }\n}'
    )
    assert selected == ["default"]


def test_presets_prefer_marimo_notebook_filename(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notebook = tmp_path / "notebook.py"
    generated_cell = tmp_path / "marimo_123" / "__marimo__cell_Xref__presets.py"
    frame = mock.Mock(filename=str(generated_cell))
    monkeypatch.setattr("moops.presets.inspect.stack", lambda: [frame, frame, frame])
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
