"""The save/rename/select preset controls shown under the script callout."""

import typing

import marimo as mo

from .presets import Presets


class PresetsUI:
    def __init__(
        self,
        presets: Presets,
        active_preset: str | None,
        select_preset: typing.Callable[[str | None], None],
        get_args: typing.Callable[[], str],
    ) -> None:
        self._presets = presets
        self._active_preset = active_preset
        self._select_preset = select_preset
        self._name_input = mo.ui.text(label="as", placeholder="default")
        self._save_btn = mo.ui.button(
            label="Save",
            on_click=lambda _: presets.save(
                self._name_input.value or "default", get_args()
            ),
        )
        rename_placeholder = (
            "preset name" if self._active_preset == "default" else "default"
        )
        self._rename_input = mo.ui.text(label="to", placeholder=rename_placeholder)
        self._rename_btn = mo.ui.button(
            label="Rename",
            on_click=lambda _: presets.rename(
                self._active_preset or "",
                self._rename_input.value or "default",
            ),
        )
        self._reset_btn = mo.ui.button(
            label="Clear changes",
            on_click=lambda _: self._select_preset(self._active_preset),
        )
        self._reset_default_btn = mo.ui.button(
            label="Reset default",
            on_click=lambda _: presets.delete("default"),
        )

    def layout(self, args: str) -> mo.Html:
        # Stored on self so the dropdown isn't garbage-collected after layout()
        # returns — mo.hstack only retains rendered HTML, not the elements, and
        # marimo's UIElementRegistry holds weakrefs. If the element is GC'd,
        # frontend interactions can't find it and on_change never fires.
        self._dropdown = mo.ui.dropdown(
            label="Preset",
            options=list(self._presets.list()),
            allow_select_none=True,
            value=self._active_preset,
            on_change=self._select_preset,
        )
        active_args = self._presets.args_for(self._active_preset)
        controls: list[typing.Any] = [self._dropdown]
        if args != active_args:
            controls.extend([self._reset_btn, self._save_btn, self._name_input])
        elif self._active_preset:
            controls.extend([self._rename_btn, self._rename_input])
        if self._active_preset is None and self._presets.default_args:
            controls.append(self._reset_default_btn)
        return mo.hstack(
            controls,
            justify="start",
        )
