import pathlib
import typing
from unittest import mock

import pytest

from moops import Group
from moops.interface import Interface
from moops.presets import Presets


def test_preset_ui_elements_stable_across_renders(tmp_path: pathlib.Path) -> None:
    presets = Presets(tmp_path / "presets.json", lambda: None, lambda _: None)
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
