import abc
import dataclasses
import math
import shlex
import sys
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _parse

Numeric = int | float

_UNSET: typing.Any = object()


@dataclasses.dataclass
class ParseError:
    message: str


@dataclasses.dataclass
class ParseResult:
    value: typing.Any


@dataclasses.dataclass
class InputControl(abc.ABC):
    """Input-channel behavior for a single UI control."""

    option: str
    help_text: str

    def options(self) -> set[str]:
        """Value options for this control."""
        return set()

    def flags(self) -> set[str]:
        """Flags for this control."""
        return set()

    @abc.abstractmethod
    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        """Parse from CLI args. Returns value, ParseError, or None if not provided."""

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        """Parse a value supplied by a URL query parameter."""

        result = self.parse(
            _parse.ParsedArgs(options={self.option: value}, unexpected=[])
        )
        assert result is not None
        return result

    @abc.abstractmethod
    def format_query_value(self, value: typing.Any) -> str | None:
        """Format a value for URL query parameters, or None to omit it."""

    @abc.abstractmethod
    def strategy(self) -> st.SearchStrategy:
        """Hypothesis strategy for generating override values."""

    @abc.abstractmethod
    def format_usage_parts(self) -> list[str]:
        """Usage tokens for this control, e.g. ['[--flag]'] or ['[--name NAME]']."""

    @abc.abstractmethod
    def format_help_lines(self) -> list[str]:
        """Help lines for this control and any aux flags."""

    @abc.abstractmethod
    def format_value(self, value: typing.Any) -> list[str]:
        """Format the command line arguments for a given value."""

    @abc.abstractmethod
    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        """Prompt the user for a value. Returns entries to inject into args.options.

        effective_default overrides self.default for display when the caller
        has a better default (e.g. from a preset).
        """


@dataclasses.dataclass
class FlagControl(InputControl):
    default: bool = False

    def flags(self) -> set[str]:
        return {self.option}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        return ParseResult(not self.default) if self.option in args.options else None

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        match value.lower():
            case "1" | "true" | "yes" | "on":
                return ParseResult(True)
            case "0" | "false" | "no" | "off":
                return ParseResult(False)
            case _:
                return ParseError(
                    f"Query parameter for {self.option} must be a boolean, "
                    f"got: {value!r}"
                )

    def strategy(self) -> st.SearchStrategy:
        return st.booleans()

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option}]"]

    def format_help_lines(self) -> list[str]:
        return [f"  {self.option}: {self.help_text}"]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [self.option]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(bool(value)).lower()

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        default_str = "y" if d else "n"
        response = input(f"{self.help_text} [y/n] (default: {default_str}): ")
        response = response.strip().lower()
        if not response:
            return {}
        wants = response in ("y", "yes", "1", "true")
        return {} if wants == self.default else {self.option: None}


@dataclasses.dataclass
class ValueControl(InputControl):
    """Base class for controls that take a value, like text or dropdowns."""

    metavar: str

    def options(self) -> set[str]:
        return {self.option}

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} {self.metavar}]"]


@dataclasses.dataclass
class TextControl(ValueControl):
    default: str

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        res = args.options.get(self.option)
        return None if res is None else ParseResult(res)

    def strategy(self) -> st.SearchStrategy:
        return st.text()

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {self.default})"
        return [line]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [f"{self.option} {shlex.quote(value)}"]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(value)

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d}]" if d else ""
        response = input(f"{self.help_text}{default_display}: ")
        return {self.option: response} if response else {}


@dataclasses.dataclass
class TextAreaControl(ValueControl):
    default: str

    @property
    def _stdin_flag(self) -> str:
        return f"{self.option}-from-stdin"

    def flags(self) -> set[str]:
        return {self._stdin_flag}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if not mo.running_in_notebook() and self._stdin_flag in args.options:
            if args.options[self._stdin_flag] is not None:
                return None
            if self.option in args.options:
                return ParseError(
                    f"Cannot use both {self.option} and {self._stdin_flag}"
                )
            return ParseResult(sys.stdin.read())
        res = args.options.get(self.option)
        return None if res is None else ParseResult(res)

    def strategy(self) -> st.SearchStrategy:
        return st.text()

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} {self.metavar} | {self._stdin_flag}]"]

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {self.default})"
        return [line, f"  {self._stdin_flag}: Read {self.option} from stdin"]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [f"{self.option} {shlex.quote(value)}"]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(value)

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d!r}]" if d else ""
        print(f"  (for multi-line input, use {self._stdin_flag} instead)")
        response = input(f"{self.help_text}{default_display}: ")
        return {self.option: response} if response else {}


@dataclasses.dataclass
class NumberControl(ValueControl):
    default: Numeric | None

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        value = args.options.get(self.option)
        return None if value is None else _parse_number(self.option, value)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(
            st.none(),
            st.integers() | st.floats(allow_nan=False, allow_infinity=False),
        )

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {self.default})"
        return [line]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [f"{self.option} {value}"]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(value)

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d}]" if d is not None else ""
        while True:
            response = input(f"{self.help_text}{default_display}: ").strip()
            if not response:
                return {}
            try:
                float(response)
                return {self.option: response}
            except ValueError:
                print("Please enter a valid number.")


@dataclasses.dataclass
class RangeControl(ValueControl):
    default: list[Numeric] | None
    start: Numeric | None = None
    stop: Numeric | None = None
    allowed_values: list[Numeric] | None = None

    @classmethod
    def from_slider(
        cls,
        *,
        option: str,
        metavar: str,
        help_text: str,
        start: Numeric | None,
        stop: Numeric | None,
        value: typing.Sequence[Numeric] | None,
        steps: typing.Sequence[Numeric] | None,
    ) -> "RangeControl":
        return cls(
            option=option,
            metavar=metavar,
            help_text=help_text,
            default=_range_default(start=start, stop=stop, value=value, steps=steps),
            start=_range_start(start=start, steps=steps),
            stop=_range_stop(stop=stop, steps=steps),
            allowed_values=list(steps) if steps is not None else None,
        )

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        raw = args.options.get(self.option)
        if raw is None:
            return None
        values = raw.split(",")
        if len(values) != 2 or not all(values):
            return ParseError(
                f"Option {self.option} expects two numbers separated by a comma, "
                f"got: {raw!r}"
            )
        parsed: list[Numeric] = []
        for value in values:
            match _parse_number(self.option, value):
                case ParseResult(value=num):
                    parsed.append(num)
                case ParseError() as err:
                    return err
        if parsed[1] < parsed[0]:
            return ParseError(
                f"Option {self.option} expects the second number to be greater "
                f"than or equal to the first, got: {raw!r}"
            )
        if self.allowed_values is not None:
            invalid = [value for value in parsed if value not in self.allowed_values]
            if invalid:
                return ParseError(
                    f"Option {self.option} values must be one of "
                    f"{self.allowed_values!r}, got: {invalid!r}"
                )
        elif (
            self.start is not None
            and self.stop is not None
            and (parsed[0] < self.start or parsed[1] > self.stop)
        ):
            return ParseError(
                f"Option {self.option} values must be between "
                f"{self.start} and {self.stop}, got: {raw!r}"
            )
        return ParseResult(parsed)

    def strategy(self) -> st.SearchStrategy:
        return st.tuples(self._number_strategy(), self._number_strategy()).map(
            lambda pair: sorted(pair)
        )

    def _number_strategy(self) -> st.SearchStrategy[Numeric]:
        if self.allowed_values is not None:
            return st.sampled_from(self.allowed_values)
        if self.start is not None and self.stop is not None:
            return st.floats(
                min_value=float(self.start),
                max_value=float(self.stop),
                allow_nan=False,
                allow_infinity=False,
            )
        return st.floats(allow_nan=False, allow_infinity=False)

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {_format_range(self.default)})"
        return [line]

    def format_value(self, value: typing.Any) -> list[str]:
        if self.default is not None and list(value) == self.default:
            return []
        return [f"{self.option} {_format_range(value)}"]

    def format_query_value(self, value: typing.Any) -> str | None:
        if self.default is not None and list(value) == self.default:
            return None
        return _format_range(value)

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        if self.allowed_values:
            print(f"  Allowed values: {', '.join(str(v) for v in self.allowed_values)}")
        elif self.start is not None and self.stop is not None:
            print(f"  Range: {self.start} to {self.stop}")
        default_display = f" [{_format_range(d)}]" if d else ""
        while True:
            response = input(f"{self.help_text} (min,max){default_display}: ").strip()
            if not response:
                return {}
            parts = response.split(",")
            if len(parts) != 2 or not all(parts):
                print("Please enter two numbers separated by a comma, e.g. 10,20")
                continue
            try:
                [float(x) for x in parts]
            except ValueError:
                print("Please enter valid numbers, e.g. 10,20")
                continue
            return {self.option: response}


@dataclasses.dataclass
class DropdownControl(InputControl):
    allowed_values: list[str]
    supports_none: bool
    default: str | None

    def options(self) -> set[str]:
        return {self.option}

    @property
    def has_no_flag(self) -> bool:
        return self.supports_none and self.default is not None

    @property
    def _no_flag(self) -> str | None:
        return f"--no-{self.option.lstrip('-')}" if self.has_no_flag else None

    def flags(self) -> set[str]:
        no_flag = self._no_flag
        return {no_flag} if no_flag else set()

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        no_flag = self._no_flag
        if no_flag and no_flag in args.options:
            if self.option in args.options:
                return ParseError(f"Cannot use both {self.option} and {no_flag}")
            return ParseResult(None)
        raw = args.options.get(self.option)
        if raw is None:
            return None
        if raw not in self.allowed_values:
            return ParseError(
                f"Option {self.option} must be one of"
                f" {self.allowed_values!r}, got: {raw!r}"
            )
        return ParseResult(raw)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        if not value and self.supports_none:
            return ParseResult(None)
        if value not in self.allowed_values:
            return ParseError(
                f"Query parameter for {self.option} must be one of"
                f" {self.allowed_values!r}, got: {value!r}"
            )
        return ParseResult(value)

    def strategy(self) -> st.SearchStrategy:
        return st.sampled_from(
            [None, *self.allowed_values] if self.supports_none else self.allowed_values
        )

    def format_usage_parts(self) -> list[str]:
        if self._no_flag:
            return [f"[{self.option} {self._values_text()} | {self._no_flag}]"]
        return [f"[{self.option} {self._values_text()}]"]

    def _values_text(self) -> str:
        return "{" + "|".join(self.allowed_values) + "}"

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self._values_text()}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {self.default})"
        lines = [line]
        if self._no_flag:
            lines.append(f"  {self._no_flag}: Set {self.option} to none")
        return lines

    def format_value(self, value: typing.Any) -> list[str]:
        if value == self.default:
            return []
        if value is None:
            assert self._no_flag
            return [self._no_flag]
        return [f"{self.option} {shlex.quote(value)}"]

    def format_query_value(self, value: typing.Any) -> str | None:
        if value == self.default:
            return None
        return "" if value is None else str(value)

    def prompt_interactive(
        self, effective_default: typing.Any = _UNSET
    ) -> dict[str, str | None]:
        d = self.default if effective_default is _UNSET else effective_default
        choices = (["none"] if self.supports_none else []) + self.allowed_values
        for i, v in enumerate(choices, 1):
            print(f"  {i}) {v}")
        default_display = f" [{d if d is not None else 'none'}]"
        while True:
            response = input(f"{self.help_text}{default_display}: ").strip()
            if not response:
                return {}
            if response.isdigit() and 1 <= int(response) <= len(choices):
                chosen = choices[int(response) - 1]
            elif response in self.allowed_values:
                chosen = response
            elif response.lower() == "none" and self.supports_none:
                chosen = "none"
            else:
                print(f"Please choose from: {', '.join(choices)}")
                continue
            if chosen == "none":
                no_flag = self._no_flag
                return {no_flag: None} if no_flag else {}
            return {self.option: chosen}


def _parse_number(option: str, value: str) -> ParseResult | ParseError:
    try:
        num = float(value)
    except ValueError:
        return ParseError(f"Option {option} expects a number, got: {value!r}")
    return ParseResult(int(num) if math.isfinite(num) and num == int(num) else num)


def _range_default(
    start: Numeric | None,
    stop: Numeric | None,
    value: typing.Sequence[Numeric] | None,
    steps: typing.Sequence[Numeric] | None,
) -> list[Numeric] | None:
    if value is not None:
        return list(value)
    if steps:
        return [steps[0], steps[-1]]
    return [start, stop] if start is not None and stop is not None else None


def _range_start(
    start: Numeric | None,
    steps: typing.Sequence[Numeric] | None,
) -> Numeric | None:
    return min(steps) if steps else start


def _range_stop(
    stop: Numeric | None,
    steps: typing.Sequence[Numeric] | None,
) -> Numeric | None:
    return max(steps) if steps else stop


def _format_range(value: typing.Iterable[typing.Any]) -> str:
    return ",".join(str(v) for v in value)
