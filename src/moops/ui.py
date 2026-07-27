from __future__ import annotations

import html
import pathlib
import typing

import marimo as mo
from marimo._output.hypertext import ContainerHtml

from . import _options


class _Fold(ContainerHtml):
    def __init__(self, child: mo.Html, summary: str) -> None:
        self._summary = summary
        super().__init__([child])

    @property
    def text(self) -> str:
        return self._build_text()

    def _build_text(self) -> str:
        child = self._children[0]
        return f"""
        <style>
          .moops-fold > summary {{
            cursor: pointer;
            list-style: none;
            width: fit-content;
          }}
          .moops-fold > summary::-webkit-details-marker {{ display: none; }}
          .moops-fold:not([open]) > summary .moops-fold-expanded {{
            display: none;
          }}
          .moops-fold[open] > summary .moops-fold-collapsed {{
            display: none;
          }}
          .moops-fold-content {{ margin-top: 0.25rem; }}
        </style>
        <details class="moops-fold">
          <summary>
            <span class="moops-fold-collapsed">&#9656; {self._summary}</span>
            <span class="moops-fold-expanded" aria-label="Collapse">&#9662;</span>
          </summary>
          <div class="moops-fold-content">{child}</div>
        </details>
        """


def fold(control: typing.Any) -> mo.Html:
    """Hide a moops control behind a compact, lazy disclosure.

    Bind the control to its own notebook variable before passing it to ``fold``
    so marimo can track its value for reactive cell execution.
    """
    input_control = getattr(control, "_moops_input", None)
    if not isinstance(input_control, _options.InputControl):
        raise TypeError("fold() requires a control created by a moops Group")

    label = input_control.label or input_control.option.lstrip("-").replace("-", " ")
    value = _display_value(control, input_control)
    value_text = _format_value(value)
    summary = html.escape(label)
    if value_text:
        summary += f" · <strong>{html.escape(value_text)}</strong>"
    return _Fold(mo.lazy(control), summary)


def _display_value(
    control: typing.Any, input_control: _options.InputControl
) -> typing.Any:
    value = getattr(control, "_value", input_control.default)
    if isinstance(input_control, (_options.FileControl, _options.MultiFileControl)):
        raw_paths = (
            typing.cast(typing.Sequence[object], value)
            if isinstance(value, (list, tuple))
            else [value]
            if value
            else []
        )
        paths = [str(getattr(item, "path", item)) for item in raw_paths]
        return (
            paths if isinstance(input_control, _options.MultiFileControl) else paths[:1]
        )
    return value


def _format_value(value: typing.Any) -> str:
    if value is None or (isinstance(value, str) and not value):
        return ""
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        values = typing.cast(typing.Sequence[object], value)
        items = [str(item) for item in values]
        if not items:
            return ""
        if len(items) <= 2:
            return ", ".join(items)
        return f"{items[0]}, {items[1]}, ... ({len(items)} selected)"
    return str(value)
