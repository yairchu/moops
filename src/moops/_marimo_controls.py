"""Helpers for reading values and structure from marimo UI control objects."""

import abc
import typing

import marimo as mo


class InputValueProvider(abc.ABC):
    """A UI wrapper that exposes its backing input control value."""

    @abc.abstractmethod
    def input_value(self) -> typing.Any:
        """Return the value shape consumed by the backing InputControl."""


def ctrl_value(ctrl: typing.Any) -> typing.Any:
    if isinstance(ctrl, InputValueProvider):
        return ctrl.input_value()
    if isinstance(ctrl, mo.ui.file_browser):
        multiple = getattr(ctrl, "_component_args", {}).get("multiple", True)
        if multiple:
            return [str(info.path) for info in ctrl.value]
        p = ctrl.path()
        return str(p) if p is not None else ""
    return ctrl._selected_key if hasattr(ctrl, "_selected_key") else ctrl.value


def ui_dictionary_elements(ctrl: typing.Any) -> dict[str, typing.Any] | None:
    elements = getattr(ctrl, "elements", None)
    return (
        typing.cast(dict[str, typing.Any], elements)
        if isinstance(elements, dict)
        else None
    )
