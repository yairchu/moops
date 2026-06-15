"""A marimo UIElement whose value is derived from a fallback moops control."""

import typing

from marimo._plugins.ui._core.ui_element import UIElement

from . import _ui_workarounds

CustomValueFn = typing.Callable[[typing.Any, typing.Any], typing.Any]


def _default_value_fn(component: typing.Any, _fallback: typing.Any) -> typing.Any:
    return component.value


class CustomElement(UIElement[typing.Any, typing.Any]):
    """A notebook component whose value is derived from a fallback control.

    ``component`` is the rendered notebook-only element (e.g. a plot selector);
    ``fallback`` is the moops control that supplies CLI behavior and defaults;
    ``value_fn(component, fallback)`` maps to the fallback-shaped value.

    The element reuses ``component``'s identity (so marimo's reactive DAG treats
    it as the same element) and implements marimo's child-element "view"
    protocol by delegating to ``component``. This lets it survive the deepcopy
    that ``mo.ui.dictionary`` performs, so ``controls_from`` can mirror it into a
    parent notebook and have the component recreated there.
    """

    def __init__(
        self,
        component: typing.Any,
        fallback: typing.Any,
        value_fn: CustomValueFn | None = None,
    ) -> None:
        if not isinstance(component, UIElement):
            raise TypeError("custom controls must build a marimo UIElement")
        self._component: UIElement[typing.Any, typing.Any] = component
        self._fallback = fallback
        self._value_fn = value_fn or _default_value_fn
        # Deliberately skip super().__init__(): we reuse the wrapped component's
        # identity so marimo's reactive DAG treats this as the same element.
        # Calling super().__init__() would register a new element and ID.
        self._id = component._id
        self._lens = component._lens

    @property
    def _value(self) -> typing.Any:
        # Computed live: in a notebook the frontend routes updates to the
        # registered component (which shares our id), not to this wrapper, so we
        # must read through to it. mo.ui.dictionary reads this attribute too.
        #
        # value_fn reads `.value` on the component and fallback, but
        # mo.ui.dictionary reads this `_value` while constructing in the same
        # cell that created them -- and marimo forbids the `.value` *property*
        # there. So hand value_fn views whose `.value` reads the unguarded
        # `_value` attribute instead; it stays live because the frontend updates
        # that attribute on the underlying element.
        return self._value_fn(
            _ui_workarounds.ValueView(self._component),
            _ui_workarounds.ValueView(self._fallback),
        )

    @property
    def value(self) -> typing.Any:
        return self._value

    @value.setter
    def value(self, value: typing.Any) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")

    def _update(self, value: typing.Any) -> None:
        self._component._update(value)

    def _on_update_completion(self) -> bool:
        return self._component._on_update_completion()

    def _register_as_view(self, parent: typing.Any, key: str) -> None:
        super()._register_as_view(parent, key)
        self._component._register_as_view(parent, key)

    def _clone(self) -> "CustomElement":
        clone = CustomElement(self._component._clone(), self._fallback, self._value_fn)
        # Preserve the input-channel link the way marimo's deepcopy-based clone
        # would (it copies __dict__), so input_map.get() still resolves the
        # mirrored clone and keeps its InputControl alive.
        moops_input = self.__dict__.get("_moops_input")
        if moops_input is not None:
            clone._moops_input = moops_input
        return clone

    def __deepcopy__(self, memo: dict[int, typing.Any]) -> "CustomElement":
        del memo
        return self._clone()

    def _mime_(self) -> tuple[str, str]:  # type: ignore[override]
        return self._component._mime_()

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._component, name)
