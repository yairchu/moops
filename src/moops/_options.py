import abc
import copy
import dataclasses
import json
import math
import pathlib
import shlex
import sys
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _choice_options, _parse, _ui_workarounds

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
    default: typing.Any
    extra_kwargs: dict[str, typing.Any] = dataclasses.field(  # type: ignore[assignment]
        default_factory=dict, kw_only=True
    )

    def options(self) -> set[str]:
        """Value options for this control."""
        return {self.option}

    def flags(self) -> set[str]:
        """Flags for this control."""
        return set()

    def allows_repeated_values(self) -> bool:
        """Whether this control accepts repeated CLI values for the same option."""
        return False

    def with_option(self, option: str) -> "InputControl":
        """Return a copy of this control with a different option name.

        Used by ``controls_from`` to re-prefix a mirrored control. Subclasses
        that wrap another control override this to re-option the inner one too.
        """
        return dataclasses.replace(self, option=option)

    @abc.abstractmethod
    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        """Parse from CLI args. Returns value, ParseError, or None if not provided."""

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        """Parse a value supplied by a URL query parameter."""

        result = self.parse(
            _parse.ParsedArgs(options={self.option: [value]}, unexpected=[])
        )
        if result is None:
            raise RuntimeError(
                f"parse() returned None for option {self.option!r} even though"
                " it was present in args — this is a bug in the control implementation"
            )
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
    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        """Create the marimo UI element for this control."""

    @abc.abstractmethod
    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        """Prompt the user for a value. Returns raw CLI tokens to append to args.

        For example, NumberControl returns ``["--factor", "2"]`` and ListControl
        in non-merged mode returns ``["--add", "--factor", "2", "--add",
        "--factor", "5"]``. The resolver appends the tokens to ``args.raw_args``
        and re-derives ``args.options`` so ``parse()`` sees them.

        effective_default overrides self.default for display when the caller
        has a better default (e.g. from a preset). An empty list means "no
        change" (user accepted the default).
        """


@dataclasses.dataclass
class FlagControl(InputControl):
    default: bool = False
    widget: typing.Literal["switch", "checkbox"] = "switch"

    def options(self) -> set[str]:
        return set()

    def flags(self) -> set[str]:
        return {self.option}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | None:
        return ParseResult(not self.default) if args.has(self.option) else None

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

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        if self.widget == "checkbox":
            return mo.ui.checkbox(
                value=value,
                label=label,
                on_change=on_change,
                disabled=disabled,
                **self.extra_kwargs,
            )
        return mo.ui.switch(
            value=value,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_str = "y" if d else "n"
        while True:
            response = input(f"{self.help_text} [y/n] (default: {default_str}): ")
            response = response.strip().lower()
            if not response:
                return []
            if response in ("y", "yes", "1", "true"):
                wants = True
            elif response in ("n", "no", "0", "false"):
                wants = False
            else:
                print("Please enter y or n.")
                continue
            return [] if wants == self.default else [self.option]


@dataclasses.dataclass
class ValueControl(InputControl):
    """Base class for controls that take a value, like text or dropdowns."""

    metavar: str

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} {self.metavar}]"]


@dataclasses.dataclass
class TextControl(ValueControl):
    default: str

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        return mo.ui.text(
            value=value,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        res = args.value_for(self.option)
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

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d}]" if d else ""
        response = input(f"{self.help_text}{default_display}: ")
        return [self.option, response] if response else []


@dataclasses.dataclass
class FileControl(TextControl):
    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        del disabled

        def _on_change(
            infos: typing.Sequence[_ui_workarounds.FileBrowserFileInfo],
        ) -> None:
            if on_change is not None:
                paths = [str(info.path) for info in infos]
                on_change(paths[0] if paths else "")

        path = str(value) if value else ""
        p = pathlib.Path(path) if path else None
        initial_path = str(p.parent) if (p and p.is_file()) else path
        browser_kwargs: dict[str, typing.Any] = dict(
            initial_path=initial_path,
            label=label,
            multiple=False,
            on_change=_on_change,
            **self.extra_kwargs,
        )
        if path:
            return _ui_workarounds.FileBrowserWithInitialSelection(
                default=[path], **browser_kwargs
            )
        return mo.ui.file_browser(**browser_kwargs)

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        result = super().parse(args)
        match result:
            case ParseResult(value=v) if v and not pathlib.Path(v).exists():
                # Empty string means no file selected; skip existence check.
                return ParseError(f"File not found: {v!r}")
            case _:
                pass
        return result

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        while True:
            result = super().prompt_interactive(effective_default)
            if not result:
                return result
            v = result[1]
            if v and not pathlib.Path(v).exists():
                print(f"File not found: {v!r}")
                continue
            return result


@dataclasses.dataclass
class MultiFileControl(ValueControl):
    default: list[str]

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        del disabled

        def _on_change(
            infos: typing.Sequence[_ui_workarounds.FileBrowserFileInfo],
        ) -> None:
            if on_change is not None:
                on_change([str(info.path) for info in infos])

        paths = list(value) if value else []
        first = paths[0] if paths else ""
        p = pathlib.Path(first) if first else None
        initial_path = str(p.parent) if (p and p.is_file()) else first
        browser_kwargs: dict[str, typing.Any] = dict(
            initial_path=initial_path,
            label=label,
            multiple=True,
            on_change=_on_change,
            **self.extra_kwargs,
        )
        if paths:
            return _ui_workarounds.FileBrowserWithInitialSelection(
                default=paths, **browser_kwargs
            )
        return mo.ui.file_browser(**browser_kwargs)

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        values = args.values_for(self.option)
        if not values:
            return None
        paths: list[str] = []
        for value in values:
            if value is None:
                return ParseError(f"Option {self.option} requires a value")
            if value and not pathlib.Path(value).exists():
                return ParseError(f"File not found: {value!r}")
            paths.append(value)
        return ParseResult(paths)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        try:
            raw: typing.Any = json.loads(value)
        except json.JSONDecodeError:
            raw = [value] if value else []
        if not isinstance(raw, list):
            return ParseError(
                f"Query parameter for {self.option} must be a JSON list of paths"
            )
        paths: list[str] = []
        for item in typing.cast(list[typing.Any], raw):
            if not isinstance(item, str):
                return ParseError(
                    f"Query parameter for {self.option} must be a JSON list of paths"
                )
            if item and not pathlib.Path(item).exists():
                return ParseError(f"File not found: {item!r}")
            paths.append(item)
        return ParseResult(paths)

    def strategy(self) -> st.SearchStrategy:
        return st.lists(st.text())

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} {self.metavar} ...]"]

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if self.default:
            line += f" (default: {', '.join(self.default)})"
        line += f" (repeat {self.option} to select multiple files)"
        return [line]

    def format_value(self, value: typing.Any) -> list[str]:
        values = list(value)
        if values == self.default:
            return []
        return [f"{self.option} {shlex.quote(v)}" for v in values]

    def format_query_value(self, value: typing.Any) -> str | None:
        values = list(value)
        return None if values == self.default else json.dumps(values)

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{', '.join(d)}]" if d else ""
        while True:
            response = input(
                f"{self.help_text} (comma-separated paths){default_display}: "
            )
            if not response:
                return []
            paths = [part.strip() for part in response.split(",") if part.strip()]
            missing = [path for path in paths if not pathlib.Path(path).exists()]
            if missing:
                print(f"File not found: {missing[0]!r}")
                continue
            return [tok for path in paths for tok in (self.option, path)]


@dataclasses.dataclass
class TextAreaControl(ValueControl):
    default: str

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        return mo.ui.text_area(
            value=value,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    @property
    def _stdin_flag(self) -> str:
        return f"{self.option}-from-stdin"

    def flags(self) -> set[str]:
        return {self._stdin_flag}

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if not mo.running_in_notebook() and args.has(self._stdin_flag):
            if args.value_for(self._stdin_flag) is not None:
                return None
            if args.has(self.option):
                return ParseError(
                    f"Cannot use both {self.option} and {self._stdin_flag}"
                )
            return ParseResult(sys.stdin.read())
        res = args.value_for(self.option)
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

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d!r}]" if d else ""
        print(f"  (for multi-line input, use {self._stdin_flag} instead)")
        response = input(f"{self.help_text}{default_display}: ")
        return [self.option, response] if response else []


@dataclasses.dataclass
class NumberControl(ValueControl):
    default: Numeric | None
    start: Numeric | None = None
    stop: Numeric | None = None
    widget: typing.Literal["number", "slider"] = "number"

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        ui_kwargs: dict[str, typing.Any] = {
            "start": self.start,
            "value": value,
            "label": label,
            "on_change": on_change,
            "disabled": disabled,
        }
        if self.stop is not None:
            ui_kwargs["stop"] = self.stop
        ui_kwargs.update(self.extra_kwargs)
        if self.widget == "slider":
            return mo.ui.slider(**ui_kwargs)
        return mo.ui.number(**ui_kwargs)

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        value = args.value_for(self.option)
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

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d}]" if d is not None else ""
        while True:
            response = input(f"{self.help_text}{default_display}: ").strip()
            if not response:
                return []
            try:
                float(response)
                return [self.option, response]
            except ValueError:
                print("Please enter a valid number.")


@dataclasses.dataclass
class RangeControl(ValueControl):
    default: list[Numeric] | None
    start: Numeric | None = None
    stop: Numeric | None = None
    allowed_values: list[Numeric] | None = None
    step: Numeric | None = None

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
        step: Numeric | None = None,
        extra_kwargs: dict[str, typing.Any] | None = None,
    ) -> "RangeControl":
        return cls(
            option=option,
            metavar=metavar,
            help_text=help_text,
            default=_range_default(start=start, stop=stop, value=value, steps=steps),
            start=_range_start(start=start, steps=steps),
            stop=_range_stop(stop=stop, steps=steps),
            allowed_values=list(steps) if steps is not None else None,
            step=step,
            extra_kwargs=extra_kwargs or {},
        )

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        return mo.ui.range_slider(
            start=self.start,
            stop=self.stop,
            step=self.step,
            steps=self.allowed_values,
            value=value,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        raw = args.value_for(self.option)
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

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        if self.allowed_values:
            print(f"  Allowed values: {', '.join(str(v) for v in self.allowed_values)}")
        elif self.start is not None and self.stop is not None:
            print(f"  Range: {self.start} to {self.stop}")
        default_display = f" [{_format_range(d)}]" if d else ""
        while True:
            response = input(f"{self.help_text} (min,max){default_display}: ").strip()
            if not response:
                return []
            parts = response.split(",")
            if len(parts) != 2 or not all(parts):
                print("Please enter two numbers separated by a comma, e.g. 10,20")
                continue
            try:
                [float(x) for x in parts]
            except ValueError:
                print("Please enter valid numbers, e.g. 10,20")
                continue
            return [self.option, response]


@dataclasses.dataclass
class MultiSelectControl(ValueControl):
    default: list[typing.Any]
    select_opts: dict[str, typing.Any]

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        selected_keys = [
            _choice_options.option_key(self.select_opts, item) for item in value
        ]
        if disabled:
            return _ui_workarounds.LockedMultiselect(
                [str(item) for item in value], label
            )
        return mo.ui.multiselect(
            options=self.select_opts,
            value=selected_keys,
            label=label,
            on_change=on_change,
            **self.extra_kwargs,
        )

    @property
    def has_no_flag(self) -> bool:
        return bool(self.default)

    @property
    def _no_flag(self) -> str | None:
        return f"--no-{self.option.lstrip('-')}" if self.has_no_flag else None

    def flags(self) -> set[str]:
        no_flag = self._no_flag
        return {no_flag} if no_flag else set()

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        no_flag = self._no_flag
        if no_flag and args.has(no_flag):
            if args.has(self.option):
                return ParseError(f"Cannot use both {self.option} and {no_flag}")
            return ParseResult([])
        values = args.values_for(self.option)
        if not values:
            return None
        result: list[typing.Any] = []
        for value in values:
            if value is None:
                return ParseError(f"Option {self.option} requires a value")
            if value not in self.select_opts:
                return ParseError(
                    f"Option {self.option} must be one of"
                    f" {list(self.select_opts)!r}, got: {value!r}"
                )
            result.append(self.select_opts[value])
        return ParseResult(result)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        try:
            raw: typing.Any = json.loads(value)
        except json.JSONDecodeError:
            raw = [value] if value else []
        if not isinstance(raw, list):
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        keys: list[str] = []
        for item in typing.cast(list[typing.Any], raw):
            if not isinstance(item, str) or item not in self.select_opts:
                return ParseError(
                    f"Query parameter for {self.option} must be a list of"
                    f" {list(self.select_opts)!r}, got item: {item!r}"
                )
            keys.append(item)
        return ParseResult([self.select_opts[item] for item in keys])

    def strategy(self) -> st.SearchStrategy:
        if not self.select_opts:
            return st.just([])
        return st.lists(st.sampled_from(list(self.select_opts.values())), unique=True)

    def format_usage_parts(self) -> list[str]:
        values_text = "{" + "|".join(self.select_opts) + "}"
        if self._no_flag:
            return [f"[{self.option} {values_text} ... | {self._no_flag}]"]
        return [f"[{self.option} {values_text} ...]"]

    def format_help_lines(self) -> list[str]:
        values_text = "{" + "|".join(self.select_opts) + "}"
        line = f"  {self.option} {values_text}: {self.help_text}"
        if self.default:
            line += (
                " (default: "
                + ", ".join(
                    _choice_options.option_key(self.select_opts, v)
                    for v in self.default
                )
                + ")"
            )
        line += f" (repeat {self.option} to select multiple)"
        lines = [line]
        if self._no_flag:
            lines.append(f"  {self._no_flag}: Clear {self.option}")
        return lines

    def format_value(self, value: typing.Any) -> list[str]:
        values = list(value)
        if values == self.default:
            return []
        if not values and self._no_flag:
            return [self._no_flag]
        return [f"{self.option} {shlex.quote(self._key_for(v))}" for v in values]

    def format_query_value(self, value: typing.Any) -> str | None:
        values = list(value)
        keys = [_choice_options.option_key(self.select_opts, v) for v in values]
        return None if values == self.default else json.dumps(keys)

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_keys = {
            _choice_options.option_key(self.select_opts, v) for v in (d or [])
        }
        for i, v in enumerate(self.select_opts, 1):
            mark = "*" if v in default_keys else " "
            print(f"  {mark}{i}) {v}")
        default_display = f" [{', '.join(default_keys)}]" if default_keys else ""
        response = input(f"{self.help_text} (comma-separated){default_display}: ")
        if not response:
            return []
        parts = [p.strip() for p in response.split(",") if p.strip()]
        return [tok for part in parts for tok in (self.option, part)]

    def _key_for(self, value: typing.Any) -> str:
        return _choice_options.option_key(self.select_opts, value)


@dataclasses.dataclass
class DropdownControl(InputControl):
    dropdown_opts: dict[str, typing.Any]
    supports_none: bool
    default: str | None

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        opts: typing.Any = (
            _ui_workarounds.locked_dropdown_options(value, self.dropdown_opts)
            if disabled
            else self.dropdown_opts
        )
        return mo.ui.dropdown(
            options=opts,
            value=value,
            label=label,
            on_change=on_change,
            **self.extra_kwargs,
        )

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
        if no_flag and args.has(no_flag):
            if args.has(self.option):
                return ParseError(f"Cannot use both {self.option} and {no_flag}")
            return ParseResult(None)
        raw = args.value_for(self.option)
        if raw is None:
            return None
        if raw not in self.dropdown_opts:
            return ParseError(
                f"Option {self.option} must be one of"
                f" {list(self.dropdown_opts)!r}, got: {raw!r}"
            )
        return ParseResult(raw)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        if not value and self.supports_none:
            return ParseResult(None)
        if value not in self.dropdown_opts:
            return ParseError(
                f"Query parameter for {self.option} must be one of"
                f" {list(self.dropdown_opts)!r}, got: {value!r}"
            )
        return ParseResult(value)

    def strategy(self) -> st.SearchStrategy:
        return st.sampled_from(
            [None, *self.dropdown_opts.keys()]
            if self.supports_none
            else list(self.dropdown_opts.keys())
        )

    def format_usage_parts(self) -> list[str]:
        if self._no_flag:
            return [f"[{self.option} {self._values_text()} | {self._no_flag}]"]
        return [f"[{self.option} {self._values_text()}]"]

    def _values_text(self) -> str:
        return "{" + "|".join(self.dropdown_opts) + "}"

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
        return next(
            (k for k, v in self.dropdown_opts.items() if v == value),
            "" if value is None else str(value),
        )

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        choices = [*(["none"] if self.supports_none else []), *self.dropdown_opts]
        for i, v in enumerate(choices, 1):
            print(f"  {i}) {v}")
        default_display = f" [{d if d is not None else 'none'}]"
        while True:
            response = input(f"{self.help_text}{default_display}: ").strip()
            if not response:
                return []
            select_none = False
            chosen = ""
            if response.isdigit() and 1 <= int(response) <= len(choices):
                idx = int(response) - 1
                select_none = self.supports_none and idx == 0
                chosen = choices[idx]
            elif response in self.dropdown_opts:
                chosen = response
            elif (
                response.lower() == "none"
                and self.supports_none
                and "none" not in self.dropdown_opts
            ):
                select_none = True
            else:
                print(f"Please choose from: {', '.join(choices)}")
                continue
            if select_none:
                no_flag = self._no_flag
                return [no_flag] if no_flag else []
            return [self.option, chosen]


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


def _get_path(
    source: typing.Any, path: tuple[str, ...], default: typing.Any
) -> typing.Any:
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
        flags = self.flags() - {self.option}
        options = {
            option: leaf.bare_control()
            for leaf in self.leaves
            for option in leaf.bare_control().options()
        }
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
                line + " (per item)"
                for leaf in self.leaves
                for line in leaf.bare_control().format_help_lines()
            ],
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        result: list[str] = []
        for item in value:
            result.append(self.option)
            for leaf in self.leaves:
                bare_control = leaf.bare_control()
                result.extend(
                    bare_control.format_value(
                        _get_path(item, leaf.value_path, bare_control.default)
                    )
                )
        return result

    def format_query_value(self, value: typing.Any) -> str | None:
        del value
        return None

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        del value
        return ParseError(
            f"Query parameters are not supported for compound list {self.option}"
        )

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
        return set() if self._is_merged else {self.option}

    def options(self) -> set[str]:
        return {self.option} if self._is_merged else self.item_control.options()

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if self._is_merged:
            raw_values = args.values_for(self.option)
            if not raw_values:
                return None
            result: list[typing.Any] = []
            for raw in raw_values:
                item_args = _parse.ParsedArgs(
                    options={self.item_control.option: [raw]}, unexpected=[]
                )
                item_result = self.item_control.parse(item_args)
                if isinstance(item_result, ParseError):
                    return item_result
                if isinstance(item_result, ParseResult):
                    result.append(item_result.value)
            return ParseResult(result)
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
        result = []
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
        flags = self.item_control.flags()
        options = self.item_control.options()
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
                if len(values) > 1 and not self.item_control.allows_repeated_values():
                    return ParseError(f"{option} was provided multiple times")
                for value in values:
                    if value is None:
                        return ParseError(f"Option {option} requires a value")
            else:
                return ParseError(f"Unexpected argument: {option}")
        return None

    def format_usage_parts(self) -> list[str]:
        if self._is_merged:
            parts = self.item_control.format_usage_parts()
            return [p[:-1] + " ...]" if p.endswith("]") else p for p in parts]
        item_usage = " ".join(self.item_control.format_usage_parts())
        return [f"[{self.option} {item_usage} ...]"]

    def format_help_lines(self) -> list[str]:
        if self._is_merged:
            lines = self.item_control.format_help_lines()
            if not lines:
                return lines
            return [lines[0] + f" (repeat {self.option} to add more)", *lines[1:]]
        return [
            f"  {self.option}: Add an item (repeat to add more)",
            *[line + " (per item)" for line in self.item_control.format_help_lines()],
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        result: list[str] = []
        for v in value:
            if not self._is_merged:
                result.append(self.option)
            formatted = self.item_control.format_value(v)
            result.extend(formatted or self._format_default_item_value(v))
        return result

    def format_query_value(self, value: typing.Any) -> str | None:
        items = list(value)
        if not items:
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
        return [f"{self.item_control.option} {shlex.quote(query_value)}"]

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


@dataclasses.dataclass
class CustomControl(InputControl):
    """A notebook-only component paired with a CLI-compatible fallback control.

    ``inner`` is the fallback control that supplies all CLI behavior (parsing,
    help, defaults, query format). ``build`` constructs the notebook component
    from the fallback's live marimo element; it is only called in notebooks.
    ``value_fn`` maps ``(component, fallback)`` to the fallback-shaped value.

    Because all CLI behavior lives in ``inner`` and the component is rebuilt by
    ``create_marimo_element``, ``controls_from`` recreates the component when it
    mirrors this control into a parent notebook.
    """

    inner: InputControl
    build: typing.Callable[[typing.Any], typing.Any]
    value_fn: typing.Callable[[typing.Any, typing.Any], typing.Any] | None = None

    # ``build`` receives the fallback's resolved *value* (a snapshot), not the
    # live element. controls_from creates the fallback and calls build in one
    # cell, and marimo forbids reading a UIElement's ``.value`` in the cell that
    # created it -- so build must not touch the element. ``value_fn`` does
    # receive the element, but it runs later (when the parent reads the mirror
    # dictionary's value), in a different cell, where ``.value`` is allowed.

    @classmethod
    def wrap(
        cls,
        inner: InputControl,
        build: typing.Callable[[typing.Any], typing.Any],
        value_fn: typing.Callable[[typing.Any, typing.Any], typing.Any] | None,
    ) -> "CustomControl":
        return cls(
            option=inner.option,
            help_text=inner.help_text,
            default=inner.default,
            inner=inner,
            build=build,
            value_fn=value_fn,
        )

    def with_option(self, option: str) -> "CustomControl":
        inner = self.inner.with_option(option)
        return dataclasses.replace(
            self, option=option, inner=inner, default=inner.default
        )

    def options(self) -> set[str]:
        return self.inner.options()

    def flags(self) -> set[str]:
        return self.inner.flags()

    def allows_repeated_values(self) -> bool:
        return self.inner.allows_repeated_values()

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        return self.inner.parse(args)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        return self.inner.parse_query_value(value)

    def format_query_value(self, value: typing.Any) -> str | None:
        return self.inner.format_query_value(value)

    def strategy(self) -> st.SearchStrategy:
        return self.inner.strategy()

    def format_usage_parts(self) -> list[str]:
        return self.inner.format_usage_parts()

    def format_help_lines(self) -> list[str]:
        return self.inner.format_help_lines()

    def format_value(self, value: typing.Any) -> list[str]:
        return self.inner.format_value(value)

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        return self.inner.prompt_interactive(effective_default)

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        fallback = self.inner.create_marimo_element(
            value, label, on_change=on_change, disabled=disabled
        )
        if not mo.running_in_notebook():
            return fallback
        from . import interface

        return interface.CustomElement(self.build(value), fallback, self.value_fn)


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
