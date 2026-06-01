"""Workarounds for marimo UI element limitations."""

import html
import pathlib
import typing

import marimo as mo
from marimo._messaging.mimetypes import KnownMimeType
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.file_browser import FileBrowserFileInfo


class ValueView:
    """Exposes a UIElement's value without tripping marimo's same-cell guard.

    `.value` reads the element's converted `_value` attribute directly, which is
    safe to read in the cell that created the element (unlike the `.value`
    property). Other attribute access delegates to the element.
    """

    def __init__(self, element: typing.Any) -> None:
        self._element = element

    @property
    def value(self) -> typing.Any:
        return self._element._value

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._element, name)


def locked_dropdown_options(
    override: str | None,
    options: list[str] | dict[str, typing.Any],
) -> list[str | None] | dict[str | None, typing.Any]:
    """Filter dropdown options to a single locked value.

    Workaround for mo.ui.dropdown not supporting disabled=True.
    See https://github.com/marimo-team/marimo/issues/9579
    """
    if isinstance(options, dict):
        return {override: None if override is None else options[override]}
    return [override]


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
        # Use the base UIElement deepcopy path so extra attributes set after
        # construction (e.g., _moops_input) are preserved on the clone.
        return super()._clone()  # type: ignore[return-value]

    def _mime_(self) -> tuple[KnownMimeType, str]:
        return ("text/html", self._html)


class FileBrowserWithInitialSelection(mo.ui.file_browser):
    """Extends mo.ui.file_browser with a CLI path fallback when no file is selected."""

    def __init__(
        self, default: str | typing.Sequence[str], **kwargs: typing.Any
    ) -> None:
        self._default = [default] if isinstance(default, str) else list(default)
        super().__init__(**kwargs)

    @property
    def value(self) -> list[FileBrowserFileInfo]:  # type: ignore[override]
        if browser_value := list(super().value):
            return browser_value
        return [
            FileBrowserFileInfo(
                id=default, path=p, name=p.name, is_directory=p.is_dir()
            )
            for default in self._default
            for p in [pathlib.Path(default)]
        ]

    @value.setter
    def value(self, value: typing.Any) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")

    def _mime_(self) -> tuple[KnownMimeType, str]:  # type: ignore[override]
        files = "\n".join({f"- `{p}`" for p in self._default})
        return mo.vstack(
            [
                mo.Html(super()._mime_()[1]),
                mo.callout(
                    mo.md(
                        "marimo's file browser "
                        "[does not yet support an initial selection]"
                        "(https://github.com/marimo-team/marimo/issues/7468). "
                        "Falling back to:\n\n"
                        f"{files}"
                    ),
                    kind="info",
                ),
            ]
        )._mime_()  # type: ignore
