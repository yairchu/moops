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
class OptionDesc:
    """Metadata for CLI options with defaults and help text."""

    default: str | None
    metavar: str
    help_text: str


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


class CliControl(abc.ABC):
    """CLI interface for a single UI control."""

    opt: OptionLabel

    @abc.abstractmethod
    def cli_info(self) -> str | OptionDesc:
        """Main option description: str for flags, OptionDesc for value options."""

    @abc.abstractmethod
    def aux_flags(self) -> dict[str, str]:
        """Extra flags for this control: {flag: help_text}."""

    @abc.abstractmethod
    def parse(self, args: _parse.ParsedArgs) -> typing.Any:
        """Parse from CLI args. Returns value, ParseError, or None if not provided."""

    @abc.abstractmethod
    def strategy(self) -> st.SearchStrategy:
        """Hypothesis strategy for generating override values."""


@dataclasses.dataclass
class FlagControl(CliControl):
    opt: OptionLabel
    help_text: str

    def cli_info(self) -> str:
        return self.help_text

    def aux_flags(self) -> dict[str, str]:
        return {}

    def parse(self, args: _parse.ParsedArgs) -> bool | None:
        return True if self.opt.option in args.options else None

    def strategy(self) -> st.SearchStrategy:
        return st.booleans()


@dataclasses.dataclass
class TextControl(CliControl):
    opt: OptionLabel
    desc: OptionDesc

    def cli_info(self) -> OptionDesc:
        return self.desc

    def aux_flags(self) -> dict[str, str]:
        return {}

    def parse(self, args: _parse.ParsedArgs) -> str | None:
        return args.options.get(self.opt.option)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(st.none(), st.text())


@dataclasses.dataclass
class TextAreaControl(CliControl):
    opt: OptionLabel
    desc: OptionDesc

    def cli_info(self) -> OptionDesc:
        return self.desc

    @property
    def _stdin_flag(self) -> str:
        return f"{self.opt.option}-from-stdin"

    def aux_flags(self) -> dict[str, str]:
        return {self._stdin_flag: f"Read {self.opt.label} from stdin"}

    def parse(self, args: _parse.ParsedArgs) -> str | _parse.ParseError | None:
        if not mo.running_in_notebook() and self._stdin_flag in args.options:
            assert args.options[self._stdin_flag] is None, (
                f"{self._stdin_flag} should not take a value"
            )
            if self.opt.option in args.options:
                return _parse.ParseError(
                    f"Cannot use both {self.opt.option} and {self._stdin_flag}"
                )
            return sys.stdin.read()
        return args.options.get(self.opt.option)

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(st.none(), st.text())


@dataclasses.dataclass
class NumberControl(CliControl):
    opt: OptionLabel
    desc: OptionDesc

    def cli_info(self) -> OptionDesc:
        return self.desc

    def aux_flags(self) -> dict[str, str]:
        return {}

    def parse(self, args: _parse.ParsedArgs) -> float | int | _parse.ParseError | None:
        value = args.options.get(self.opt.option)
        if value is None:
            return None
        try:
            num = float(value)
        except ValueError:
            return _parse.ParseError(
                f"Option {self.opt.option} expects a number, got: {value!r}"
            )
        return int(num) if math.isfinite(num) and num == int(num) else num

    def strategy(self) -> st.SearchStrategy:
        return st.one_of(
            st.none(),
            st.integers() | st.floats(allow_nan=False, allow_infinity=False),
        )


@dataclasses.dataclass
class DropdownControl(CliControl):
    opt: OptionLabel
    desc: OptionDesc
    allowed_values: list[str]
    supports_none: bool

    def cli_info(self) -> OptionDesc:
        return self.desc

    @property
    def has_no_flag(self) -> bool:
        return self.supports_none and self.desc.default is not None

    @property
    def _no_flag(self) -> str | None:
        return f"--no-{self.opt.option.lstrip('-')}" if self.has_no_flag else None

    def aux_flags(self) -> dict[str, str]:
        no_flag = self._no_flag
        return {no_flag: f"Set {self.opt.label} to none"} if no_flag else {}

    def parse(
        self, args: _parse.ParsedArgs
    ) -> _parse.DropdownValue | _parse.ParseError | None:
        no_flag = self._no_flag
        if no_flag and no_flag in args.options:
            if self.opt.option in args.options:
                return _parse.ParseError(
                    f"Cannot use both {self.opt.option} and {no_flag}"
                )
            return _parse.DropdownValue(None)
        raw = args.options.get(self.opt.option)
        if raw is None:
            return None
        if raw not in self.allowed_values:
            return _parse.ParseError(
                f"Option {self.opt.option} must be one of"
                f" {self.allowed_values!r}, got: {raw!r}"
            )
        return _parse.DropdownValue(raw)

    def strategy(self) -> st.SearchStrategy:
        base: st.SearchStrategy = st.sampled_from(self.allowed_values)
        if self.has_no_flag:
            base = st.one_of(st.none(), base)
        return st.one_of(st.none(), base)


@dataclasses.dataclass
class ControlMeta:
    cli: CliControl
    overridden: bool = False
    control_ref: weakref.ref[typing.Any] | None = dataclasses.field(
        default=None, repr=False, compare=False
    )


class ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(
        self, controls: tuple[typing.Any], control_meta: dict[int, ControlMeta]
    ) -> None:
        self.flags: dict[str, str] = {}
        self.str_options: dict[str, OptionDesc] = {}
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
            info = meta.cli.cli_info()
            if isinstance(info, str):
                self.flags[meta.cli.opt.option] = info
            else:
                self.str_options[meta.cli.opt.option] = info
            self.flags.update(meta.cli.aux_flags())

    def format_help(self, command: str) -> str:
        options = [
            *[f"[{x}]" for x in self.flags],
            *[f"[{k} {v.metavar}]" for k, v in self.str_options.items()],
            "[-h/--help]",
        ]
        segments = [f"Usage: {command.rsplit('/', 1)[-1]} {' '.join(options)}"]
        opts_help = [f"  {k}: {v}" for k, v in self.flags.items()]
        opts_help.extend(
            f"  {k} {v.metavar}: {v.help_text}"
            f"{f' (default: {v.default})' if v.default else ''}"
            for k, v in self.str_options.items()
        )
        if opts_help:
            segments.append("\n".join(opts_help))
        return "\n\n".join(segments)

    def validate(
        self, args: _parse.ParsedArgs, validation_errors: dict[str, str]
    ) -> typing.Iterator[str]:
        rendered = self.flags | self.str_options
        yield from (v for k, v in validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in args.unexpected:
            yield f"{unexp_text}{x}"
        for k, v in args.options.items():
            if k in self.flags:
                if v is not None:
                    yield f"{k} does not take a value, but was given: {v}"
            elif k in self.str_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in _parse.help_flags:
                yield f"{unexp_text}{k}"
