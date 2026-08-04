from __future__ import annotations

import dataclasses
import json
import typing

import marimo as mo

from . import _list_options, _options, _parse

if typing.TYPE_CHECKING:
    from hypothesis import strategies as st

ScalarType = type[str] | type[int] | type[float]
_UNSET: typing.Any = object()


def _type_name(scalar_type: ScalarType) -> str:
    return {str: "TEXT", int: "INTEGER", float: "NUMBER"}[scalar_type]


def _parse_scalar(
    option: str, raw: str, scalar_type: ScalarType, role: str
) -> _options.ParseResult | _options.ParseError:
    if scalar_type is str:
        return _options.ParseResult(raw)
    try:
        return _options.ParseResult(scalar_type(raw))
    except ValueError:
        return _options.ParseError(
            f"Option {option} expects {role} to be {_type_name(scalar_type).lower()}, "
            f"got: {raw!r}"
        )


def _parse_entry(
    option: str, raw: str, key_type: ScalarType, value_type: ScalarType
) -> _options.ParseResult | _options.ParseError:
    if "=" not in raw:
        return _options.ParseError(f"Option {option} expects KEY=VALUE, got: {raw!r}")
    raw_key, raw_value = raw.split("=", 1)
    if not raw_key:
        return _options.ParseError(
            f"Option {option} expects a non-empty key in KEY=VALUE, got: {raw!r}"
        )
    key_result = _parse_scalar(option, raw_key, key_type, "the key")
    if isinstance(key_result, _options.ParseError):
        return key_result
    value_result = _parse_scalar(option, raw_value, value_type, "the value")
    if isinstance(value_result, _options.ParseError):
        return value_result
    return _options.ParseResult((key_result.value, value_result.value))


def _format_entry(key: typing.Any, value: typing.Any) -> str:
    return f"{key}={value}"


class _MappingUI:
    def __init__(
        self,
        list_ui: typing.Any,
        *,
        key_type: ScalarType,
        value_type: ScalarType,
    ) -> None:
        self._list_ui = list_ui
        self._key_type = key_type
        self._value_type = value_type
        self._id = list_ui._id
        if hasattr(list_ui, "_add_btn"):
            self._add_btn = list_ui._add_btn

    @property
    def value(self) -> dict[typing.Any, typing.Any]:
        result: dict[typing.Any, typing.Any] = {}
        for entry in self._list_ui.value:
            key = self._key_type(entry["key"])
            value = self._value_type(entry["value"])
            result[key] = value
        return result

    def _mime_(self) -> typing.Any:
        return self._list_ui._mime_()


@dataclasses.dataclass
class MappingControl(_options.InputControl):
    key_type: ScalarType
    value_type: ScalarType

    def allows_repeated_values(self) -> bool:
        return True

    def parse(
        self, args: _parse.ParsedArgs
    ) -> _options.ParseResult | _options.ParseError | None:
        values = args.values_for(self.option)
        if not values:
            return None
        result: dict[typing.Any, typing.Any] = {}
        for raw in values:
            if raw is None:
                return _options.ParseError(f"Option {self.option} requires KEY=VALUE")
            parsed = _parse_entry(self.option, raw, self.key_type, self.value_type)
            if isinstance(parsed, _options.ParseError):
                return parsed
            key, value = typing.cast(tuple[typing.Any, typing.Any], parsed.value)
            if key in result:
                return _options.ParseError(
                    f"Option {self.option} received duplicate key: {key!r}"
                )
            result[key] = value
        return _options.ParseResult(result)

    def parse_query_value(
        self, value: str
    ) -> _options.ParseResult | _options.ParseError:
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return _options.ParseError(
                f"Query parameter for {self.option} must be a JSON object"
            )
        if not isinstance(raw, dict):
            return _options.ParseError(
                f"Query parameter for {self.option} must be a JSON object"
            )
        raw_mapping = typing.cast(dict[str, typing.Any], raw)
        entries: list[str | None] = [
            _format_entry(key, item_value) for key, item_value in raw_mapping.items()
        ]
        return self.parse(
            _parse.ParsedArgs(options={self.option: entries}, unexpected=[])
        ) or _options.ParseResult({})

    def format_query_value(self, value: typing.Any) -> str | None:
        mapping = dict(value)
        return None if mapping == self.default else json.dumps(mapping)

    def strategy(self) -> st.SearchStrategy:
        from hypothesis import strategies as st

        def scalar_strategy(scalar_type: ScalarType) -> st.SearchStrategy:
            if scalar_type is str:
                return st.text(min_size=1)
            if scalar_type is int:
                return st.integers()
            return st.floats(allow_nan=False, allow_infinity=False)

        return st.dictionaries(
            scalar_strategy(self.key_type), scalar_strategy(self.value_type)
        )

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} KEY=VALUE ...]"]

    def format_help_lines(self) -> list[str]:
        line = (
            f"  {self.option} "
            f"{_type_name(self.key_type)}={_type_name(self.value_type)}: "
            f"{self.help_text}"
        )
        if self.default:
            defaults = ", ".join(
                _format_entry(key, value) for key, value in self.default.items()
            )
            line += f" (default: {defaults})"
        line += f" (repeat {self.option} to set multiple entries)"
        return [line]

    def format_value(self, value: typing.Any) -> list[str]:
        mapping = dict(value)
        if mapping == self.default:
            return []
        return [
            _options.option_value_token(self.option, _format_entry(key, item_value))
            for key, item_value in mapping.items()
        ]

    def format_value_groups(self, value: typing.Any) -> list[list[str]]:
        return [[token] for token in self.format_value(value)]

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        del label
        mapping = dict(value)
        if self.key_type is str:
            key: typing.Any = "key"
            suffix = 2
            while key in mapping:
                key = f"key{suffix}"
                suffix += 1
        else:
            key = 0
            while key in mapping:
                key += 1
            if self.key_type is float:
                key = float(key)
        default_entry = {
            "key": key,
            "value": "" if self.value_type is str else 0,
        }
        elements: list[typing.Any] = []

        def current_entries() -> list[dict[str, typing.Any]]:
            return [dict(element.value) for element in elements]

        def handle_change(entries: list[dict[str, typing.Any]]) -> None:
            if on_change is None:
                return
            result: dict[typing.Any, typing.Any] = {}
            for entry in entries:
                entry_key = self.key_type(entry["key"])
                if entry_key in result:
                    return
                result[entry_key] = self.value_type(entry["value"])
            on_change(result)

        def handle_edit(index: int, field: str, new_value: typing.Any) -> None:
            entries = current_entries()
            entries[index][field] = new_value
            handle_change(entries)

        def scalar_element(
            scalar_type: ScalarType,
            scalar_value: typing.Any,
            field_label: str,
            on_edit: typing.Callable[[typing.Any], None] | None,
        ) -> typing.Any:
            if scalar_type is str:
                return mo.ui.text(
                    value=str(scalar_value),
                    label=field_label,
                    on_change=on_edit,
                    disabled=disabled,
                )
            return mo.ui.number(
                value=typing.cast(float, scalar_type(scalar_value)),
                label=field_label,
                step=1 if scalar_type is int else None,
                on_change=on_edit,
                disabled=disabled,
            )

        for index, (entry_key, entry_value) in enumerate(mapping.items()):
            key_element = scalar_element(
                self.key_type,
                entry_key,
                "Key",
                (
                    lambda new_value, i=index: (
                        handle_edit(i, "key", new_value)
                        if on_change is not None
                        else None
                    )
                ),
            )
            value_element = scalar_element(
                self.value_type,
                entry_value,
                "Value",
                (
                    lambda new_value, i=index: (
                        handle_edit(i, "value", new_value)
                        if on_change is not None
                        else None
                    )
                ),
            )
            element = mo.ui.dictionary({"key": key_element, "value": value_element})

            def row_elements(
                entry_elements: tuple[typing.Any, typing.Any] = (
                    key_element,
                    value_element,
                ),
            ) -> list[typing.Any]:
                return list(entry_elements)

            element._moops_row_elements = row_elements
            elements.append(element)

        array = mo.ui.array(elements)
        if on_change is not None and mo.running_in_notebook():
            display, add_btn = _list_options._build_list_ui(  # pyright: ignore[reportPrivateUsage]
                elements,
                current_items=current_entries,
                default_item=lambda: dict(default_entry),
                set_items=handle_change,
            )
            list_ui: typing.Any = _list_options._ListUI(  # pyright: ignore[reportPrivateUsage]
                array,
                add_btn,
                display=display,
                value_getter=current_entries,
            )
        else:
            list_ui = array
        return _MappingUI(
            list_ui,
            key_type=self.key_type,
            value_type=self.value_type,
        )

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        default = self.default if effective_default is _UNSET else effective_default
        default_display = (
            " ["
            + ", ".join(_format_entry(key, value) for key, value in default.items())
            + "]"
            if default
            else ""
        )
        response = input(
            f"{self.help_text} (comma-separated KEY=VALUE){default_display}: "
        ).strip()
        if not response:
            return []
        return [
            token
            for entry in response.split(",")
            for token in (self.option, entry.strip())
        ]
