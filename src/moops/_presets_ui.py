"""The save/rename/select preset controls shown under the script callout."""

import typing

import marimo as mo

from .presets import PendingCliInput, Presets


class PresetsUI:
    def __init__(
        self,
        presets: Presets,
        active_preset: str | None,
        select_preset: typing.Callable[[str | None], None],
        get_args: typing.Callable[[], str],
        apply_cli_args: typing.Callable[[str], tuple[str, ...]],
        pending_cli: PendingCliInput | None,
    ) -> None:
        self._presets = presets
        self._active_preset = active_preset
        self._select_preset = select_preset
        self._apply_cli_args = apply_cli_args
        self._pending_cli = pending_cli
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

    def command_box(self, command: str) -> mo.Html:
        """The editable command line shown in the script callout.

        Editing commits on blur: the text is parsed as a full CLI invocation
        and every control is initialized from it. A failed parse reshows the
        user's text (with the errors, see ``layout``) so they can fix it; an
        accepted one shows the current command for further editing.

        Stored on self so the element isn't garbage-collected after the
        callout renders — see ``layout``'s note on weakrefs and on_change.
        """
        self._command_input = mo.ui.text_area(
            value=self._pending_cli.text if self._pending_cli is not None else command,
            on_change=self._on_command_change,
            full_width=True,
        )
        return self._command_input

    def pending_errors(self) -> tuple[str, ...]:
        """Errors from the last failed command-box edit (``()`` if none).

        Rendered by the root callout (see ``Interface._root_panel``) rather
        than here, so the whole callout can turn into an alert.
        """
        return self._pending_cli.errors if self._pending_cli is not None else ()

    def _on_command_change(self, text: str) -> None:
        errors = self._apply_cli_args(text)
        if errors:
            self._presets.set_pending_cli(PendingCliInput(text, errors))
        else:
            # apply_cli_args has written the parsed values to the query params;
            # deselecting the preset both makes those win on the rerun (an
            # active preset otherwise overrides query params) and clears any
            # pending error. Setting the user's mo.state is also what triggers
            # the rerun in the first place — query-param writes alone re-run
            # nothing, since no notebook cell holds a reference to that state.
            self._presets.select(None)

    def layout(self, args: str) -> mo.Html:
        # Stored on self so the elements aren't garbage-collected after layout()
        # returns — mo.hstack only retains rendered HTML, not the elements, and
        # marimo's UIElementRegistry holds weakrefs. If an element is GC'd,
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
        return mo.hstack(controls, justify="start")
