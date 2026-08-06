"""Higher-level controls composed from Group primitives."""

from __future__ import annotations

import typing

import marimo as mo

from .group import Group

ScalarType = type[str] | type[int] | type[float]


def _parse_scalar(raw: typing.Any, scalar_type: ScalarType, role: str) -> typing.Any:
    if scalar_type is str:
        return str(raw)
    try:
        parsed = scalar_type(raw)
        if scalar_type is int and not isinstance(raw, str) and parsed != raw:
            raise ValueError
        return parsed
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Mapping {role} must be {scalar_type.__name__}, got {raw!r}"
        ) from exc


def _parse_entry(
    raw: str, key_type: ScalarType, value_type: ScalarType
) -> tuple[typing.Any, typing.Any]:
    if "=" not in raw:
        raise ValueError(f"Mapping entry must be KEY=VALUE, got {raw!r}")
    raw_key, raw_value = raw.split("=", 1)
    if not raw_key:
        raise ValueError(f"Mapping entry key must not be empty, got {raw!r}")
    return (
        _parse_scalar(raw_key, key_type, "key"),
        _parse_scalar(raw_value, value_type, "value"),
    )


def _format_entry(key: typing.Any, value: typing.Any) -> str:
    if isinstance(key, str) and "=" in key:
        raise ValueError("Mapping key must not contain =")
    return f"{key}={value}"


def _mapping_value(
    entries: typing.Iterable[str],
    key_type: ScalarType,
    value_type: ScalarType,
) -> dict[typing.Any, typing.Any]:
    result: dict[typing.Any, typing.Any] = {}
    for raw in entries:
        key, value = _parse_entry(raw, key_type, value_type)
        if key in result:
            raise ValueError(f"Mapping contains duplicate key: {key!r}")
        result[key] = value
    return result


class Mapping:
    """A dictionary-valued view over a list of KEY=VALUE entries."""

    def __init__(
        self,
        entries: typing.Any,
        key_type: ScalarType,
        value_type: ScalarType,
    ) -> None:
        self._entries = entries
        self._list_ui = entries
        self._key_type = key_type
        self._value_type = value_type
        self._id = entries._id
        self._moops_input = entries._moops_input
        if hasattr(entries, "_add_btn"):
            self._add_btn = entries._add_btn

    @property
    def value(self) -> dict[typing.Any, typing.Any]:
        return _mapping_value(self._entries.value, self._key_type, self._value_type)

    @property
    def _moops_input_value(self) -> list[str]:
        return list(self._entries.value)

    def _moops_reset_state(self, value: typing.Any) -> None:
        reset_state = getattr(self._entries, "_moops_reset_state", None)
        if callable(reset_state):
            reset_state(value)

    def _mime_(self) -> typing.Any:
        return self._entries._mime_()


def mapping(
    group: Group,
    *,
    option: str,
    help_text: str,
    key: ScalarType = str,
    value: ScalarType = str,
    label: str | None = None,
    default: typing.Mapping[typing.Any, typing.Any] | None = None,
    on_change: typing.Callable[[dict[typing.Any, typing.Any]], None] | None = None,
) -> Mapping:
    """Create a dictionary-valued composite backed by Group.list().

    Each CLI occurrence uses KEY=VALUE syntax. In notebooks each list item
    renders separate typed Key and Value widgets. The first equals sign
    separates the key from the value, so string keys must not contain ``=``.
    """
    if key not in (str, int, float) or value not in (str, int, float):
        raise TypeError("mapping key and value must be str, int, or float")
    initial = dict(default or {})
    initial_entries = [_format_entry(k, v) for k, v in initial.items()]
    _mapping_value(initial_entries, key, value)
    if key is str:
        next_key: typing.Any = "key"
        suffix = 2
        while next_key in initial:
            next_key = f"key{suffix}"
            suffix += 1
    else:
        next_key = 0
        while next_key in initial:
            next_key += 1
        if key is float:
            next_key = float(next_key)
    default_entry = _format_entry(next_key, "" if value is str else value(0))

    def item(item_group: Group) -> typing.Any:
        fallback = item_group.text(
            option=option,
            value=default_entry,
            help_text=help_text,
        )

        def build(raw: str) -> typing.Any:
            entry_key, entry_value = _parse_entry(raw, key, value)
            key_element = (
                mo.ui.text(value=str(entry_key), label="Key")
                if key is str
                else mo.ui.number(
                    value=typing.cast(float, entry_key),
                    step=1 if key is int else None,
                    label="Key",
                )
            )
            value_element = (
                mo.ui.text(value=str(entry_value), label="Value")
                if value is str
                else mo.ui.number(
                    value=typing.cast(float, entry_value),
                    step=1 if value is int else None,
                    label="Value",
                )
            )
            component = mo.ui.dictionary({"key": key_element, "value": value_element})
            component._moops_row_elements = lambda: [
                component.elements["key"],
                component.elements["value"],
            ]

            def component_is_valid() -> bool:
                raw_key = getattr(component.elements["key"], "_value", None)
                raw_value = getattr(component.elements["value"], "_value", None)
                if raw_key is None or raw_value is None:
                    return False
                try:
                    _parse_scalar(raw_key, key, "key")
                    _parse_scalar(raw_value, value, "value")
                except ValueError:
                    return False
                return True

            component._moops_should_forward_change = component_is_valid
            return component

        def entry_value(component: typing.Any, fallback: typing.Any) -> str:
            component_elements = getattr(component, "elements", None)
            if not isinstance(component_elements, dict):
                return str(fallback.value)
            elements = typing.cast(dict[str, typing.Any], component_elements)
            raw_key = elements["key"]._value
            raw_value = elements["value"]._value
            if raw_key is None or raw_value is None:
                return str(fallback.value)
            try:
                return _format_entry(
                    _parse_scalar(raw_key, key, "key"),
                    _parse_scalar(raw_value, value, "value"),
                )
            except ValueError:
                return str(fallback.value)

        return item_group.custom(fallback, build, value=entry_value)

    def entries_changed(entries: list[str]) -> None:
        if on_change is None:
            return
        try:
            parsed = _mapping_value(entries, key, value)
        except ValueError:
            return
        on_change(parsed)

    def validate_entries(entries: list[typing.Any]) -> str | None:
        try:
            _mapping_value(entries, key, value)
        except ValueError as exc:
            return str(exc)
        return None

    entries = group.list(
        item,
        option=option,
        help_text=help_text,
        label=label,
        value=initial_entries,
        on_change=entries_changed if on_change is not None else None,
        _value_validator=validate_entries,
    )
    return Mapping(entries, key, value)
