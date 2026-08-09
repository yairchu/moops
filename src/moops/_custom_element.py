"""A marimo UIElement whose value is derived from a fallback moops control."""

import dataclasses
import typing

from marimo._plugins.ui._core.ui_element import UIElement

from . import _ui_workarounds

CustomValueFn = typing.Callable[[typing.Any, typing.Any], typing.Any]


@dataclasses.dataclass(frozen=True)
class CustomComponentBehavior:
    """Optional integration behavior for a custom notebook component.

    Composite controls use this adapter instead of installing ad-hoc attributes
    on marimo elements. The functions receive the current component, including
    a cloned component, so behavior survives view cloning without mutation.
    """

    change_sources: typing.Callable[[typing.Any], list[typing.Any]] | None = None
    accepts_change: typing.Callable[[typing.Any], bool] | None = None


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
        behavior: CustomComponentBehavior | None = None,
    ) -> None:
        if not isinstance(component, UIElement):
            raise TypeError("custom controls must build a marimo UIElement")
        self._component: UIElement[typing.Any, typing.Any] = component
        self._fallback = fallback
        self._value_fn = value_fn or _default_value_fn
        self._behavior = behavior or CustomComponentBehavior()
        # Deliberately skip super().__init__(): we reuse the wrapped component's
        # identity so marimo's reactive DAG treats this as the same element.
        # Calling super().__init__() would register a new element and ID.
        self._id = component._id
        self._lens = component._lens
        self._attach_change_forwarding()

    def _attach_change_forwarding(self) -> None:
        fallback_on_change = getattr(self._fallback, "_on_change", None)
        if not callable(fallback_on_change):
            return

        sources = self.row_elements()
        for source in sources:
            previous_on_change = getattr(source, "_on_change", None)
            if getattr(previous_on_change, "_moops_custom_bridge", False):
                previous_on_change = getattr(
                    previous_on_change, "_moops_previous_on_change", None
                )

            def forward_change(
                new_value: typing.Any,
                *,
                changed_source: typing.Any = source,
                previous: typing.Any = previous_on_change,
            ) -> None:
                # UIElement._update sets this before invoking _on_change. Set it
                # here as well so direct callback invocation behaves identically
                # in tests and other programmatic integrations.
                changed_source._value = new_value
                if callable(previous):
                    previous(new_value)
                accepts_change = self._behavior.accepts_change
                if accepts_change is not None and not accepts_change(self._component):
                    return
                fallback_on_change(self._value)

            forward_change._moops_custom_bridge = True  # type: ignore[attr-defined]
            forward_change._moops_previous_on_change = previous_on_change  # type: ignore[attr-defined]
            source._on_change = forward_change

    def row_elements(self) -> list[typing.Any]:
        """Return the component elements to lay out and observe for changes."""
        change_sources = self._behavior.change_sources
        return (
            change_sources(self._component)
            if change_sources is not None
            else [self._component]
        )

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

    @_value.setter
    def _value(self, value: typing.Any) -> None:
        # Interface resets supply values in the fallback control's shape. The
        # arbitrary notebook component may use a different frontend value, so
        # leave it untouched; the accepted CLI edit triggers a notebook rerun
        # that rebuilds the component from this fallback value.
        self._fallback._value = value

    def _moops_reset_state(self, value: typing.Any) -> None:
        """Delegate query-state resets to the CLI fallback control."""
        reset_state = getattr(self._fallback, "_moops_reset_state", None)
        if callable(reset_state):
            reset_state(value)

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
        component = self._component._clone()
        clone = CustomElement(
            component, self._fallback, self._value_fn, behavior=self._behavior
        )
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
