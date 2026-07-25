"""Workarounds for marimo UI element limitations."""

import typing


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
