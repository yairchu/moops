"""Workarounds for marimo UI elements that lack `disabled` support."""

import html

from marimo._messaging.mimetypes import KnownMimeType
from marimo._plugins.ui._core.ui_element import UIElement


class LockedMultiselect(UIElement[str, list[str]]):
    """Read-only multiselect placeholder used when a control is overridden.

    Workaround for mo.ui.multiselect not supporting disabled=True.
    See https://github.com/marimo-team/marimo/issues/9579
    """

    def __init__(self, value: list[str], label_html: str) -> None:
        self._locked_value = list(value)
        self._label_html = label_html
        _chips = "".join(
            f'<span style="background:var(--sky-2,#dbeafe);border-radius:4px;'
            f'padding:2px 8px;margin:2px;display:inline-block">{v}</span>'
            for v in [html.escape(item) for item in value]
        )
        self._html = (
            f'<div style="padding:4px 0;opacity:0.7">'
            f"{label_html}: {_chips or '(none)'}"
            f"</div>"
        )
        display_value = ", ".join(value) if value else "(none)"
        super().__init__(
            component_name="marimo-text",
            initial_value=display_value,
            label=label_html,
            on_change=None,
            args={
                "placeholder": "",
                "kind": "text",
                "max-length": None,
                "full-width": False,
                "disabled": True,
                "debounce": True,
                "password-has-value": None,
            },
        )

    def _convert_value(self, value: str) -> list[str]:
        del value
        return list(self._locked_value)

    def _clone(self) -> "LockedMultiselect":
        return LockedMultiselect(list(self._locked_value), self._label_html)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        return ("text/html", self._html)
