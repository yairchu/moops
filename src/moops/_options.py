import abc
import dataclasses
import math
import sys
import typing
import weakref

import marimo as mo
from hypothesis import strategies as st

from . import _parse, interface


@dataclasses.dataclass
class OptionLabel:
    """Maps between UI labels and CLI option names."""

    label: str
    option: str

    @staticmethod
    def make(
        label: str | None, option: str | None, prefix: str | None = None
    ) -> "OptionLabel":
        """Generate OptionLabel from label or option name."""

        if option is None:
            assert label is not None, "Either label or option must be provided"
            option = f"--{prefix or ''}{label.lower().replace(' ', '-')}"
        else:
            assert option.startswith("-"), f"Option must start with dash: {option}"
            assert prefix is None or option.startswith(f"--{prefix}"), (
                f"Option {option} must start with --{prefix}"
            )
            if label is None:
                label = option.lstrip("-").replace("-", " ")
        return OptionLabel(label=label, option=option)


@dataclasses.dataclass
class ParseError:
    message: str


@dataclasses.dataclass
class ParseResult:
    value: typing.Any


@dataclasses.dataclass
class CliControl(abc.ABC):
    """CLI interface for a single UI control."""

    opt: OptionLabel
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


@dataclasses.dataclass
class FlagControl(CliControl):
    default: bool = False

    def flags(self) -> set[str]:
        return {self.opt.option}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        if self.opt.option not in args.options:
            return None
        return ParseResult(not self.default)

    def strategy(self) -> st.SearchStrategy:
        return st.booleans()

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.opt.option}]"]

    def format_help_lines(self) -> list[str]:
        return [f"  {self.opt.option}: {self.help_text}"]


@dataclasses.dataclass
class ValueControl(CliControl):
    """Base class for controls that take a value, like text or dropdowns."""

    metavar: str

    def options(self) -> set[str]:
        return {self.opt.option}

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.opt.option} {self.metavar}]"]


@dataclasses.dataclass
class TextControl(ValueControl):
    default: str

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        res = args.options.get(self.opt.option)
        return None if res is None else ParseResult(res)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(st.none(), st.text())

    def format_help_lines(self) -> list[str]:
        line = f"  {self.opt.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {self.default})"
        return [line]


@dataclasses.dataclass
class TextAreaControl(ValueControl):
    default: str

    @property
    def _stdin_flag(self) -> str:
        return f"{self.opt.option}-from-stdin"

    def flags(self) -> set[str]:
        return {self._stdin_flag}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if not mo.running_in_notebook() and self._stdin_flag in args.options:
            assert args.options[self._stdin_flag] is None, (
                f"{self._stdin_flag} should not take a value"
            )
            if self.opt.option in args.options:
                return ParseError(
                    f"Cannot use both {self.opt.option} and {self._stdin_flag}"
                )
            return ParseResult(sys.stdin.read())
        res = args.options.get(self.opt.option)
        return None if res is None else ParseResult(res)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(st.none(), st.text())

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.opt.option} {self.metavar}]", f"[{self._stdin_flag}]"]

    def format_help_lines(self) -> list[str]:
        line = f"  {self.opt.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {self.default})"
        return [line, f"  {self._stdin_flag}: Read {self.opt.label} from stdin"]


@dataclasses.dataclass
class NumberControl(ValueControl):
    default: float | int | None

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        value = args.options.get(self.opt.option)
        if value is None:
            return None
        try:
            num = float(value)
        except ValueError:
            return ParseError(
                f"Option {self.opt.option} expects a number, got: {value!r}"
            )
        return ParseResult(int(num) if math.isfinite(num) and num == int(num) else num)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(
            st.none(),
            st.integers() | st.floats(allow_nan=False, allow_infinity=False),
        )

    def format_help_lines(self) -> list[str]:
        line = f"  {self.opt.option} {self.metavar}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {self.default})"
        return [line]


@dataclasses.dataclass
class DropdownControl(CliControl):
    allowed_values: list[str]
    supports_none: bool
    default: str | None

    def options(self) -> set[str]:
        return {self.opt.option}

    @property
    def has_no_flag(self) -> bool:
        return self.supports_none and self.default is not None

    @property
    def _no_flag(self) -> str | None:
        return f"--no-{self.opt.option.lstrip('-')}" if self.has_no_flag else None

    def flags(self) -> set[str]:
        no_flag = self._no_flag
        return {no_flag} if no_flag else set()

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        no_flag = self._no_flag
        if no_flag and no_flag in args.options:
            if self.opt.option in args.options:
                return ParseError(f"Cannot use both {self.opt.option} and {no_flag}")
            return ParseResult(None)
        raw = args.options.get(self.opt.option)
        if raw is None:
            return None
        if raw not in self.allowed_values:
            return ParseError(
                f"Option {self.opt.option} must be one of"
                f" {self.allowed_values!r}, got: {raw!r}"
            )
        return ParseResult(raw)

    def strategy(self) -> st.SearchStrategy:
        return st.sampled_from(
            [None, *self.allowed_values] if self.supports_none else self.allowed_values
        )

    def format_usage_parts(self) -> list[str]:
        parts = [f"[{self.opt.option} {self._values_text()}]"]
        if self._no_flag:
            parts.append(f"[{self._no_flag}]")
        return parts

    def _values_text(self) -> str:
        return "{" + "|".join(self.allowed_values) + "}"

    def format_help_lines(self) -> list[str]:
        line = f"  {self.opt.option} {self._values_text()}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {self.default})"
        lines = [line]
        if self._no_flag:
            lines.append(f"  {self._no_flag}: Set {self.opt.label} to none")
        return lines


@dataclasses.dataclass
class ControlMeta:
    cli: CliControl
    overridden: bool = False
    option_prefix: str = ""
    control_ref: weakref.ref[typing.Any] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )


class ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(
        self, controls: tuple[typing.Any], control_meta: dict[int, ControlMeta]
    ) -> None:
        self._controls: list[CliControl] = []
        self.flags: set[str] = set()
        self.value_options: set[str] = set()
        seen: set[str] = set()
        for ctrl in interface.Interface(controls).flatten():
            meta = control_meta.get(id(ctrl))
            if meta is None:
                raise ValueError(f"Control {ctrl!r} was not created by this Group")
            if meta.cli.opt.option in seen:
                raise ValueError(
                    f"Option {meta.cli.opt.option!r} "
                    f"passed to interface() more than once"
                )
            seen.add(meta.cli.opt.option)
            if meta.overridden:
                continue
            self.value_options.update(meta.cli.options())
            self.flags.update(meta.cli.flags())
            self._controls.append(meta.cli)

    def format_help(self, command: str) -> str:
        usage_parts = [p for ctrl in self._controls for p in ctrl.format_usage_parts()]
        usage_parts.append("[-h/--help]")
        segments = [f"Usage: {command.rsplit('/', 1)[-1]} {' '.join(usage_parts)}"]
        help_lines = [
            line for ctrl in self._controls for line in ctrl.format_help_lines()
        ]
        if help_lines:
            segments.append("\n".join(help_lines))
        return "\n\n".join(segments)

    def validate(
        self, args: _parse.ParsedArgs, validation_errors: dict[str, str]
    ) -> typing.Iterator[str]:
        rendered = self.flags | self.value_options
        yield from (v for k, v in validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in args.unexpected:
            yield f"{unexp_text}{x}"
        for k, v in args.options.items():
            if k in self.flags:
                if v is not None:
                    yield f"{k} does not take a value, but was given: {v}"
            elif k in self.value_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in _parse.help_flags:
                yield f"{unexp_text}{k}"
