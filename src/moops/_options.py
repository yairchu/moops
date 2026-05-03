import abc
import dataclasses
import math
import shlex
import sys
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _parse


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
            assert args.options[self._stdin_flag] is None, (
                f"{self._stdin_flag} should not take a value"
            )
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
    default: float | int | None

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        value = args.options.get(self.option)
        if value is None:
            return None
        try:
            num = float(value)
        except ValueError:
            return ParseError(f"Option {self.option} expects a number, got: {value!r}")
        return ParseResult(int(num) if math.isfinite(num) and num == int(num) else num)

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
