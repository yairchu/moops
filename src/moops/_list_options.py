from __future__ import annotations

import copy
import dataclasses
import json
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _options, _parse, _variant

InputControl = _options.InputControl
ParseError = _options.ParseError
ParseResult = _options.ParseResult

_UNSET: typing.Any = object()


class _ListUI:
    """Notebook UI wrapper for a list control with add/remove buttons."""

    def __init__(
        self,
        array: typing.Any,
        add_btn: typing.Any,
        remove_btn: typing.Any,
        *,
        display: typing.Any | None = None,
        value_getter: typing.Callable[[], list[typing.Any]] | None = None,
    ) -> None:
        self._array = array
        self._display = display if display is not None else array
        self._value_getter = value_getter
        self._add_btn = add_btn
        self._remove_btn = remove_btn
        self._id = array._id

    @property
    def value(self) -> list[typing.Any]:
        if self._value_getter is not None:
            return self._value_getter()
        return list(self._array.value)

    def _mime_(self) -> typing.Any:
        combined = mo.vstack(
            [self._display, mo.hstack([self._add_btn, self._remove_btn])]
        )
        return combined._mime_()  # type: ignore[reportPrivateUsage]


class _ElementList:
    """Minimal array-like adapter for live child elements."""

    def __init__(self, elements: list[typing.Any]) -> None:
        self.elements = elements
        fallback_id = f"list-{id(self)}"
        self._id = getattr(elements[0], "_id", fallback_id) if elements else fallback_id

    @property
    def value(self) -> list[typing.Any]:
        return [element.value for element in self.elements]


@dataclasses.dataclass(frozen=True)
class SubgroupListLeaf:
    value_path: tuple[str, ...]
    control: InputControl
    bare_option: str
    variant_selector_bare_option: str | None = None
    variant_key: str | None = None

    def bare_control(self) -> InputControl:
        return self.control.with_option(self.bare_option)


def _option_key(token: str) -> str:
    return token.split("=", 1)[0]


def _is_option_token(token: str) -> bool:
    return token.startswith("-") and not (
        len(token) > 1 and token[0] == "-" and token[1].isdigit()
    )


def _segment_by_anchor(
    raw_args: list[str],
    anchor: str,
    *,
    item_options: set[str] | None = None,
    item_flags: set[str] | None = None,
) -> list[list[str]]:
    """Split raw_args into per-item segments at each bare anchor occurrence."""
    segments: list[list[str]] = []
    current: list[str] | None = None
    expecting_item_value = False
    for token in raw_args:
        if token == anchor:
            if current is not None:
                segments.append(current)
            current = []
            expecting_item_value = False
        elif current is not None:
            if expecting_item_value:
                current.append(token)
                expecting_item_value = False
                continue
            if _is_option_token(token) and item_options is not None:
                option = _option_key(token)
                if option in item_options:
                    current.append(token)
                    expecting_item_value = "=" not in token
                    continue
                if item_flags is not None and option in item_flags:
                    current.append(token)
                    expecting_item_value = False
                    continue
                segments.append(current)
                current = None
                expecting_item_value = False
                continue
            current.append(token)
    if current is not None:
        segments.append(current)
    return segments


def _validate_item_placement(
    raw_args: list[str],
    anchor: str,
    item_options: set[str],
    item_flags: set[str],
) -> ParseError | None:
    in_item = False
    expecting_item_value = False
    item_args = item_options | item_flags
    for token in raw_args:
        if token == anchor:
            in_item = True
            expecting_item_value = False
        elif in_item and expecting_item_value:
            expecting_item_value = False
        elif in_item and _is_option_token(token):
            option = _option_key(token)
            if option in item_options:
                expecting_item_value = "=" not in token
            elif option in item_flags:
                expecting_item_value = False
            else:
                in_item = False
                expecting_item_value = False
        elif not in_item and _option_key(token) in item_args:
            return ParseError(f"Unexpected argument: {_option_key(token)}")
    return None


def _set_path(
    target: dict[str, typing.Any], path: tuple[str, ...], value: typing.Any
) -> None:
    current = target
    for part in path[:-1]:
        child = current.setdefault(part, {})
        if not isinstance(child, dict):
            raise TypeError(f"Cannot assign nested list item value at {path!r}")
        current = typing.cast(dict[str, typing.Any], child)
    current[path[-1]] = value


def get_path(
    source: typing.Any, path: tuple[str, ...], default: typing.Any
) -> typing.Any:
    """Read the value at ``path`` in nested dicts, returning ``default`` if absent."""
    current: typing.Any = source
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = typing.cast(dict[str, typing.Any], current)[part]
    return current


def _element_at_path(root: typing.Any, path: tuple[str, ...]) -> typing.Any | None:
    current: typing.Any = root
    for part in path:
        elements: typing.Any = getattr(current, "elements", None)
        if not isinstance(elements, dict) or part not in elements:
            return None
        current = typing.cast(dict[str, typing.Any], elements)[part]
    return current


def _validate_item_args(
    args: _parse.ParsedArgs,
    flags: set[str],
    options: dict[str, InputControl],
) -> ParseError | None:
    """Validate parsed args for a single list item against its item controls."""
    for unexpected in args.unexpected:
        return ParseError(f"Unexpected argument: {unexpected}")
    for option, values in args.options.items():
        if option in flags:
            for value in values:
                if value is not None:
                    return ParseError(
                        f"{option} does not take a value, but was given: {value}"
                    )
        elif option in options:
            control = options[option]
            if len(values) > 1 and not control.allows_repeated_values():
                return ParseError(f"{option} was provided multiple times")
            for value in values:
                if value is None:
                    return ParseError(f"Option {option} requires a value")
        else:
            return ParseError(f"Unexpected argument: {option}")
    return None


def _leaf_was_provided(args: _parse.ParsedArgs, leaf: SubgroupListLeaf) -> str | None:
    bare_control = leaf.bare_control()
    return next(
        (
            option
            for option in bare_control.options() | bare_control.flags()
            if args.has(option)
        ),
        None,
    )


@dataclasses.dataclass
class SubgroupListControl(InputControl):
    """A list whose items are mirrored subgroup interfaces."""

    item_template_default: dict[str, typing.Any]
    leaves: tuple[SubgroupListLeaf, ...]
    item_builder: typing.Callable[[int, dict[str, typing.Any]], typing.Any]
    default: list[dict[str, typing.Any]]

    def options(self) -> set[str]:
        return {
            option for leaf in self.leaves for option in leaf.bare_control().options()
        }

    def flags(self) -> set[str]:
        return {
            self.option,
            *(flag for leaf in self.leaves for flag in leaf.bare_control().flags()),
        }

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if err := self._validate_item_placement(args.raw_args):
            return err
        segments = _segment_by_anchor(
            args.raw_args,
            self.option,
            item_options=self.options(),
            item_flags=self.flags() - {self.option},
        )
        if not segments:
            return None
        result: list[dict[str, typing.Any]] = []
        for segment in segments:
            item_args = _parse.ParsedArgs.from_options(segment)
            if err := self._validate_item_args(item_args):
                return err
            item_value = copy.deepcopy(self.item_template_default)
            for leaf in self.leaves:
                bare_control = leaf.bare_control()
                leaf_result = bare_control.parse(item_args)
                if isinstance(leaf_result, ParseError):
                    return leaf_result
                value = (
                    leaf_result.value
                    if isinstance(leaf_result, ParseResult)
                    else bare_control.default
                )
                _set_path(item_value, leaf.value_path, value)
            if err := self._validate_active_variant_leaf_args(item_args, item_value):
                return err
            result.append(item_value)
        return ParseResult(result)

    def _validate_item_placement(self, raw_args: list[str]) -> ParseError | None:
        return _validate_item_placement(
            raw_args,
            self.option,
            self.options(),
            self.flags() - {self.option},
        )

    def _validate_item_args(self, args: _parse.ParsedArgs) -> ParseError | None:
        return _validate_item_args(
            args,
            self.flags() - {self.option},
            {
                option: leaf.bare_control()
                for leaf in self.leaves
                for option in leaf.bare_control().options()
            },
        )

    def _validate_active_variant_leaf_args(
        self, args: _parse.ParsedArgs, item_value: dict[str, typing.Any]
    ) -> ParseError | None:
        selector_paths = self._variant_selector_paths()
        for leaf in self.leaves:
            if self._is_active_variant_leaf(leaf, item_value, selector_paths):
                continue
            if provided := _leaf_was_provided(args, leaf):
                return ParseError(f"Unexpected argument: {provided}")
        return None

    def _variant_selector_paths(self) -> dict[str, tuple[str, ...]]:
        return {
            option: leaf.value_path
            for leaf in self.leaves
            for option in leaf.bare_control().options() | leaf.bare_control().flags()
        }

    def _is_active_variant_leaf(
        self,
        leaf: SubgroupListLeaf,
        item_value: dict[str, typing.Any],
        selector_paths: dict[str, tuple[str, ...]],
    ) -> bool:
        if leaf.variant_selector_bare_option is None or leaf.variant_key is None:
            return True
        selector_path = selector_paths.get(leaf.variant_selector_bare_option)
        if selector_path is None:
            return True
        selected = get_path(item_value, selector_path, _UNSET)
        return selected is _UNSET or leaf.variant_key == _variant.key_text(selected)

    def format_usage_parts(self) -> list[str]:
        inner = " ".join(
            part
            for leaf in self.leaves
            for part in leaf.bare_control().format_usage_parts()
        )
        return [f"[{self.option} {inner} ...]"]

    def format_help_lines(self) -> list[str]:
        return [
            f"  {self.option}: Add an item (repeat to add more)",
            *[
                f"{line} (per item)"
                for leaf in self.leaves
                for line in leaf.bare_control().format_help_lines()
            ],
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        return [token for group in self.format_value_groups(value) for token in group]

    def format_value_groups(self, value: typing.Any) -> list[list[str]]:
        selector_paths = self._variant_selector_paths()
        groups: list[list[str]] = []
        for item in value:
            group = [self.option]
            for leaf in self.leaves:
                if not self._is_active_variant_leaf(leaf, item, selector_paths):
                    continue
                bare_control = leaf.bare_control()
                group.extend(
                    bare_control.format_value(
                        get_path(item, leaf.value_path, bare_control.default)
                    )
                )
            groups.append(group)
        return groups

    def format_query_value(self, value: typing.Any) -> str | None:
        try:
            return json.dumps(value)
        except TypeError:
            return None

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        try:
            raw_items: typing.Any = json.loads(value)
        except json.JSONDecodeError:
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        if not isinstance(raw_items, list):
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        return ParseResult(raw_items)

    def strategy(self) -> st.SearchStrategy:
        leaf_strategies = {
            leaf.value_path: leaf.bare_control().strategy() for leaf in self.leaves
        }

        def assemble(
            values: dict[tuple[str, ...], typing.Any],
        ) -> dict[str, typing.Any]:
            item = copy.deepcopy(self.item_template_default)
            for path, value in values.items():
                _set_path(item, path, value)
            return item

        return st.lists(st.fixed_dictionaries(leaf_strategies).map(assemble))

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        del label, disabled
        items = [copy.deepcopy(item) for item in value]
        elements = [self.item_builder(i, item) for i, item in enumerate(items)]
        if on_change is not None and mo.running_in_notebook():
            self._attach_item_change_handlers(elements, on_change)

            def value_getter() -> list[typing.Any]:
                return [element.value for element in elements]

            add_btn = mo.ui.button(
                label="+ Add",
                on_click=lambda _: on_change(
                    [*value_getter(), copy.deepcopy(self.item_template_default)]
                ),
            )
            remove_btn = mo.ui.button(
                label="- Remove",
                on_click=lambda _: (
                    on_change(value_getter()[:-1]) if value_getter() else None
                ),
            )
            return _ListUI(
                _ElementList(elements),
                add_btn,
                remove_btn,
                display=mo.vstack(elements),
                value_getter=value_getter,
            )
        return mo.ui.array(elements)

    def _attach_item_change_handlers(
        self,
        item_elements: list[typing.Any],
        on_change: typing.Callable[[typing.Any], None],
    ) -> None:
        def value_getter() -> list[typing.Any]:
            return [element.value for element in item_elements]

        for idx, item_element in enumerate(item_elements):
            for leaf in self.leaves:
                element = _element_at_path(item_element, leaf.value_path)
                if element is not None:
                    self._attach_leaf_change_handler(
                        value_getter, idx, leaf.value_path, element, on_change
                    )

    def _attach_leaf_change_handler(
        self,
        value_getter: typing.Callable[[], list[typing.Any]],
        idx: int,
        path: tuple[str, ...],
        element: typing.Any,
        on_change: typing.Callable[[typing.Any], None],
    ) -> None:
        previous_on_change = getattr(element, "_on_change", None)

        def handle_change(new_value: typing.Any) -> None:
            if callable(previous_on_change):
                previous_on_change(new_value)
            items = [copy.deepcopy(item) for item in value_getter()]
            if idx >= len(items):
                return
            _set_path(items[idx], path, new_value)
            on_change(items)

        element._on_change = handle_change

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        del effective_default
        if not self.leaves:
            return []
        tokens: list[str] = []
        first_leaf, *remaining_leaves = self.leaves
        while True:
            first_tokens = first_leaf.bare_control().prompt_interactive()
            if not first_tokens:
                break
            tokens.append(self.option)
            tokens.extend(first_tokens)
            for leaf in remaining_leaves:
                tokens.extend(leaf.bare_control().prompt_interactive())
        return tokens


@dataclasses.dataclass
class ListControl(InputControl):
    """A list of repeated items with a shared anchor option.

    Merged mode (option == item option): each ``--factor VALUE`` occurrence
    is one item. Non-merged mode (option != item option): each bare ``--add``
    starts a new item and the following per-item options belong to it.
    """

    item_control: InputControl
    default: list[typing.Any]

    @property
    def _is_merged(self) -> bool:
        return self.option == self.item_control.option

    def flags(self) -> set[str]:
        if self._is_merged:
            return self.item_control.flags()
        # Non-merged: the anchor plus any per-item flags (e.g. a dropdown's
        # --no-tag) must all be recognized by the top-level parser, matching
        # what format_help_lines/format_usage_parts advertise.
        return {self.option} | self.item_control.flags()

    def options(self) -> set[str]:
        return {self.option} if self._is_merged else self.item_control.options()

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if self._is_merged:
            return self._parse_merged_items(args.raw_args)
        if err := self._validate_non_merged_item_placement(args.raw_args):
            return err
        segments = _segment_by_anchor(
            args.raw_args,
            self.option,
            item_options=self.item_control.options(),
            item_flags=self.item_control.flags(),
        )
        if not segments:
            return None
        result: list[typing.Any] = []
        for segment in segments:
            item_args = _parse.ParsedArgs.from_options(segment)
            if err := self._validate_item_args(item_args):
                return err
            item_result = self.item_control.parse(item_args)
            if isinstance(item_result, ParseError):
                return item_result
            result.append(
                item_result.value
                if isinstance(item_result, ParseResult)
                else self.item_control.default
            )
        return ParseResult(result)

    def _validate_non_merged_item_placement(
        self, raw_args: list[str]
    ) -> ParseError | None:
        return _validate_item_placement(
            raw_args,
            self.option,
            self.item_control.options(),
            self.item_control.flags(),
        )

    def _validate_item_args(self, args: _parse.ParsedArgs) -> ParseError | None:
        return _validate_item_args(
            args,
            self.item_control.flags(),
            dict.fromkeys(self.item_control.options(), self.item_control),
        )

    def _parse_merged_items(
        self, raw_args: list[str]
    ) -> ParseResult | ParseError | None:
        result: list[typing.Any] = []
        found = False
        item_flags = self.item_control.flags()
        i = 0
        while i < len(raw_args):
            token = raw_args[i]
            option = _option_key(token)
            if option == self.option:
                segment = [token]
                if "=" not in token and i + 1 < len(raw_args):
                    next_token = raw_args[i + 1]
                    if not _is_option_token(next_token):
                        segment.append(next_token)
                        i += 1
                found = True
            elif option in item_flags:
                segment = [token]
                found = True
            else:
                i += 1
                continue
            item_result = self.item_control.parse(
                _parse.ParsedArgs.from_options(segment)
            )
            if isinstance(item_result, ParseError):
                return item_result
            if isinstance(item_result, ParseResult):
                result.append(item_result.value)
            i += 1
        return ParseResult(result) if found else None

    def format_usage_parts(self) -> list[str]:
        if self._is_merged:
            parts = self.item_control.format_usage_parts()
            return [f"{p[:-1]} ...]" if p.endswith("]") else p for p in parts]
        item_usage = " ".join(self.item_control.format_usage_parts())
        return [f"[{self.option} {item_usage} ...]"]

    def format_help_lines(self) -> list[str]:
        if self._is_merged:
            lines = self.item_control.format_help_lines()
            if not lines:
                return lines
            return [f"{lines[0]} (repeat {self.option} to add more)", *lines[1:]]
        return [
            f"  {self.option}: Add an item (repeat to add more)",
            *[f"{line} (per item)" for line in self.item_control.format_help_lines()],
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        return [token for group in self.format_value_groups(value) for token in group]

    def format_value_groups(self, value: typing.Any) -> list[list[str]]:
        groups: list[list[str]] = []
        for v in value:
            formatted = self.item_control.format_value(v)
            if not self._is_merged:
                # The anchor already represents the item, so an item that
                # formats to no per-item token (e.g. an empty multiselect)
                # needs no filler — the merged-mode fallback would emit a
                # token the parser then rejects.
                groups.append([self.option, *formatted])
            else:
                groups.append(formatted or self._format_default_item_value(v))
        return groups

    def format_query_value(self, value: typing.Any) -> str | None:
        items = list(value)
        if not items and not self.default:
            return None
        return json.dumps([self.item_control.format_query_value(v) for v in items])

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        try:
            raw_items: typing.Any = json.loads(value)
        except json.JSONDecodeError:
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        if not isinstance(raw_items, list):
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        result: list[typing.Any] = []
        for raw_item in typing.cast(list[typing.Any], raw_items):
            if raw_item is None:
                result.append(self.item_control.default)
                continue
            item_result = self.item_control.parse_query_value(str(raw_item))
            if isinstance(item_result, ParseError):
                return item_result
            result.append(item_result.value)
        return ParseResult(result)

    def _format_default_item_value(self, value: typing.Any) -> list[str]:
        query_value = self.item_control.format_query_value(value)
        if query_value is None:
            query_value = str(value)
        return [_options.option_value_token(self.item_control.option, query_value)]

    def strategy(self) -> st.SearchStrategy:
        return st.lists(self.item_control.strategy())

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        items = list(value)

        def make_item_on_change(
            idx: int,
            notify: typing.Callable[[typing.Any], None],
        ) -> typing.Callable[[typing.Any], None]:
            def handler(new_val: typing.Any) -> None:
                new_list = list(items)
                new_list[idx] = new_val
                notify(new_list)

            return handler

        elements = [
            self.item_control.create_marimo_element(
                v,
                label=f"{label} [{i + 1}]",
                disabled=disabled,
                on_change=make_item_on_change(i, on_change) if on_change else None,
            )
            for i, v in enumerate(items)
        ]
        array = mo.ui.array(elements)
        if on_change is not None and mo.running_in_notebook():
            item_default = self.item_control.default
            add_btn = mo.ui.button(
                label="+ Add",
                on_click=lambda _: on_change([*items, item_default]),
            )
            remove_btn = mo.ui.button(
                label="- Remove",
                on_click=lambda _: on_change(items[:-1]) if items else None,
            )
            return _ListUI(array, add_btn, remove_btn)
        return array

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        tokens: list[str] = []
        while True:
            item_tokens = self.item_control.prompt_interactive()
            if not item_tokens:
                break
            if not self._is_merged:
                tokens.append(self.option)
            tokens.extend(item_tokens)
        return tokens
