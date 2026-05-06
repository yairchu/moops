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


@dataclasses.dataclass
class ParseError:
    message: str


@dataclasses.dataclass
class ParseResult:
    value: typing.Any


@dataclasses.dataclass
class CliControl(abc.ABC):
    """CLI interface for a single UI control."""

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


@dataclasses.dataclass
class FlagControl(CliControl):
    default: bool = False

    def flags(self) -> set[str]:
        return {self.option}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        return ParseResult(not self.default) if self.option in args.options else None

    def strategy(self) -> st.SearchStrategy:
        return st.booleans()

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option}]"]

    def format_help_lines(self) -> list[str]:
        return [f"  {self.option}: {self.help_text}"]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [self.option]


@dataclasses.dataclass
class ValueControl(CliControl):
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
        return [f"[{self.option} {self.metavar}]", f"[{self._stdin_flag}]"]

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {self.default})"
        return [line, f"  {self._stdin_flag}: Read {self.option} from stdin"]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [f"{self.option} {shlex.quote(value)}"]


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


@dataclasses.dataclass
class RangeControl(ValueControl):
    default: list[Numeric] | None
    start: Numeric | None = None
    stop: Numeric | None = None
    allowed_values: list[Numeric] | None = None

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


@dataclasses.dataclass
class DropdownControl(CliControl):
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

    def strategy(self) -> st.SearchStrategy:
        return st.sampled_from(
            [None, *self.allowed_values] if self.supports_none else self.allowed_values
        )

    def format_usage_parts(self) -> list[str]:
        parts = [f"[{self.option} {self._values_text()}]"]
        if self._no_flag:
            parts.append(f"[{self._no_flag}]")
        return parts

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


def _parse_number(option: str, value: str) -> ParseResult | ParseError:
    try:
        num = float(value)
    except ValueError:
        return ParseError(f"Option {option} expects a number, got: {value!r}")
    return ParseResult(int(num) if math.isfinite(num) and num == int(num) else num)


def _format_range(value: typing.Iterable[typing.Any]) -> str:
    return ",".join(str(v) for v in value)
