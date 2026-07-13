from __future__ import annotations

import abc
import contextlib
import dataclasses
import json
import math
import pathlib
import shlex
import sys
import typing

import marimo as mo

from . import _choice_options, _custom_element, _parse, _ui_workarounds

if typing.TYPE_CHECKING:
    from hypothesis import strategies as st

Numeric = int | float

_UNSET: typing.Any = object()


def option_value_token(option: str, value: str) -> str:
    """Serialize an ``option value`` pair as one CLI token string.

    A value starting with ``-`` would be re-tokenized as a separate option by
    ``_parse.ParsedArgs.from_options`` (which has no per-option spec to know the
    value belongs to ``option``), so emit it as ``option=value``, which
    ``from_options`` parses unambiguously. Other values use the plain
    ``option value`` form. The value is shell-quoted either way.
    """
    quoted = shlex.quote(value)
    return f"{option}={quoted}" if value.startswith("-") else f"{option} {quoted}"


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
    # Resolved display label, stashed at registration so controls_from can
    # mirror it. None until registered; the mirror falls back to the option
    # name. Travels through with_option's dataclasses.replace.
    label: str | None = dataclasses.field(default=None, kw_only=True)
    extra_kwargs: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict[str, typing.Any], kw_only=True
    )
    # Set by Group.custom(): a factory that builds a notebook-only component
    # from this control's resolved value, and a value_fn mapping
    # (component, fallback) to the control's value shape. When set, make_element
    # wraps the control's own element in a CustomElement in notebooks; the
    # control keeps all its CLI/parse/help behavior as the fallback.
    custom_build: typing.Callable[[typing.Any], typing.Any] | None = dataclasses.field(
        default=None, kw_only=True
    )
    custom_value_fn: _custom_element.CustomValueFn | None = dataclasses.field(
        default=None, kw_only=True
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

    def with_option(self, option: str) -> InputControl:
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

    def format_value_groups(self, value: typing.Any) -> list[list[str]]:
        """Format args split into wrap-friendly groups of tokens.

        Each group is kept together on one line when the script-callout command
        is wrapped. The default is a single group holding all of this control's
        tokens; the list control overrides this to emit one group per item so
        long repeated-option commands wrap per item instead of overflowing.
        """
        tokens = self.format_value(value)
        return [tokens] if tokens else []

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

    def make_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        """Create this control's element, applying any Group.custom() wrapper.

        Ordinary controls just return ``create_marimo_element``; a control set up
        by ``Group.custom()`` wraps that element in a ``CustomElement`` (notebook
        only) so it renders a bespoke component while keeping this control's CLI
        fallback. Use this instead of ``create_marimo_element`` wherever an
        element is built from a control that may carry a custom wrapper.
        """
        if "disabled" in self.extra_kwargs:
            raise TypeError("disabled is managed by moops")
        element = self.create_marimo_element(
            value, label, on_change=on_change, disabled=disabled
        )
        if self.custom_build is None or not mo.running_in_notebook():
            return element
        return _custom_element.CustomElement(
            self.custom_build(value), element, self.custom_value_fn
        )

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


class _NoneFlag:
    """Shared ``--no-<option>`` handling for controls whose value can be a
    "none"/cleared sentinel: a dropdown's ``None``, an empty multiselect, or a
    cleared unbounded number.

    Each control supplies :attr:`_has_no_flag` (whether the flag applies) and
    passes the sentinel value to :meth:`_parse_none_flag`; the flag name,
    registration, and usage/help formatting are shared here.
    """

    option: str  # provided by the InputControl subclass

    @property
    def _has_no_flag(self) -> bool:
        """Whether this control exposes a ``--no-<option>`` flag."""
        raise NotImplementedError

    @property
    def _no_flag(self) -> str | None:
        return f"--no-{self.option.lstrip('-')}" if self._has_no_flag else None

    def flags(self) -> set[str]:
        no_flag = self._no_flag
        return {no_flag} if no_flag else set()

    def _parse_none_flag(
        self, args: _parse.ParsedArgs, none_value: typing.Any
    ) -> ParseResult | ParseError | None:
        """Return the sentinel result if ``--no-<option>`` is present (or an
        error if combined with the value option), else None to keep parsing."""
        no_flag = self._no_flag
        if no_flag and args.has(no_flag):
            if args.has(self.option):
                return ParseError(f"Cannot use both {self.option} and {no_flag}")
            return ParseResult(none_value)
        return None

    def _usage_with_no_flag(self, inner: str) -> str:
        if self._no_flag:
            return f"[{self.option} {inner} | {self._no_flag}]"
        return f"[{self.option} {inner}]"

    def _help_no_flag_line(self, description: str) -> list[str]:
        return [f"  {self._no_flag}: {description}"] if self._no_flag else []


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
        from hypothesis import strategies as st

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

    def _help_line(self, *, show_default: bool) -> str:
        line = f"  {self.option} {self.metavar}: {self.help_text}"
        if show_default:
            line += f" (default: {self.default})"
        return line


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
        from hypothesis import strategies as st

        return st.text()

    def format_help_lines(self) -> list[str]:
        return [self._help_line(show_default=bool(self.default))]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [option_value_token(self.option, value)]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(value)

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d}]" if d else ""
        response = input(f"{self.help_text}{default_display}: ")
        return [self.option, response] if response else []


def _create_file_browser(
    first_path: str,
    default_paths: list[str],
    *,
    label: str,
    multiple: bool,
    on_change: typing.Callable[
        [typing.Sequence[_ui_workarounds.FileBrowserFileInfo]], None
    ],
    extra_kwargs: dict[str, typing.Any],
) -> typing.Any:
    p = pathlib.Path(first_path) if first_path else None
    initial_path = str(p.parent) if (p and p.is_file()) else first_path
    browser_kwargs: dict[str, typing.Any] = dict(
        initial_path=initial_path,
        label=label,
        multiple=multiple,
        on_change=on_change,
        **extra_kwargs,
    )
    if default_paths:
        return _ui_workarounds.FileBrowserWithInitialSelection(
            default=default_paths, **browser_kwargs
        )
    return mo.ui.file_browser(**browser_kwargs)


def _decode_json_list(value: str) -> list[typing.Any] | None:
    try:
        raw: typing.Any = json.loads(value)
    except json.JSONDecodeError:
        raw = [value] if value else []
    if not isinstance(raw, list):
        return None
    return typing.cast(list[typing.Any], raw)


def _missing_path_error(value: str) -> ParseError | None:
    if value and not pathlib.Path(value).exists():
        return ParseError(f"File not found: {value!r}")
    return None


def _file_browser_paths(value: typing.Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, pathlib.Path):
        return [str(value)]
    if isinstance(value, typing.Sequence):
        items = typing.cast(typing.Sequence[object], value)
        return [
            str(item.path)
            if isinstance(item, _ui_workarounds.FileBrowserFileInfo)
            else str(item)
            for item in items
        ]
    return [str(value)]


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
        return _create_file_browser(
            path,
            [path] if path else [],
            label=label,
            multiple=False,
            on_change=_on_change,
            extra_kwargs=self.extra_kwargs,
        )

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        result = super().parse(args)
        match result:
            case ParseResult(value=v):
                return _missing_path_error(v) or result
            case _:
                pass
        return result

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        while True:
            result = super().prompt_interactive(effective_default)
            if not result:
                return result
            v = result[1]
            if err := _missing_path_error(v):
                print(err.message)
                continue
            return result

    def format_value(self, value: typing.Any) -> list[str]:
        paths = _file_browser_paths(value)
        return super().format_value(paths[0] if paths else "")

    def format_query_value(self, value: typing.Any) -> str | None:
        paths = _file_browser_paths(value)
        return super().format_query_value(paths[0] if paths else "")


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
        return _create_file_browser(
            paths[0] if paths else "",
            paths,
            label=label,
            multiple=True,
            on_change=_on_change,
            extra_kwargs=self.extra_kwargs,
        )

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
            if err := _missing_path_error(value):
                return err
            paths.append(value)
        return ParseResult(paths)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        raw = _decode_json_list(value)
        if raw is None:
            return ParseError(
                f"Query parameter for {self.option} must be a JSON list of paths"
            )
        paths: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                return ParseError(
                    f"Query parameter for {self.option} must be a JSON list of paths"
                )
            if err := _missing_path_error(item):
                return err
            paths.append(item)
        return ParseResult(paths)

    def strategy(self) -> st.SearchStrategy:
        from hypothesis import strategies as st

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
        values = _file_browser_paths(value)
        if values == self.default:
            return []
        return [option_value_token(self.option, v) for v in values]

    def format_query_value(self, value: typing.Any) -> str | None:
        values = _file_browser_paths(value)
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
            errors = [err for path in paths if (err := _missing_path_error(path))]
            if errors:
                print(errors[0].message)
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
        from hypothesis import strategies as st

        return st.text()

    def format_usage_parts(self) -> list[str]:
        return [f"[{self.option} {self.metavar} | {self._stdin_flag}]"]

    def format_help_lines(self) -> list[str]:
        return [
            self._help_line(show_default=bool(self.default)),
            f"  {self._stdin_flag}: Read {self.option} from stdin",
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        return [] if value == self.default else [option_value_token(self.option, value)]

    def format_query_value(self, value: typing.Any) -> str | None:
        return None if value == self.default else str(value)

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        default_display = f" [{d!r}]" if d else ""
        print(f"  (for multi-line input, use {self._stdin_flag} instead)")
        response = input(f"{self.help_text}{default_display}: ")
        return [self.option, response] if response else []


@dataclasses.dataclass
class NumberControl(_NoneFlag, ValueControl):
    default: Numeric | None
    start: Numeric | None = None
    stop: Numeric | None = None
    widget: typing.Literal["number", "slider"] = "number"
    allow_none: bool = True

    @property
    def _widget_allows_none(self) -> bool:
        """Whether the widget can actually hold None.

        Only an unbounded number input keeps a None value; bounded numbers and
        sliders coerce None to their start, so None is never a real state there.
        """
        return self.widget == "number" and self.start is None and self.stop is None

    @property
    def _is_none_capable(self) -> bool:
        return self.allow_none and self._widget_allows_none

    @property
    def _has_no_flag(self) -> bool:
        # A non-None default needs a distinct token for None, since absence of
        # the option already means "use the default".
        return self._is_none_capable and self.default is not None

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
        if (none_result := self._parse_none_flag(args, None)) is not None:
            return none_result
        value = args.value_for(self.option)
        if value is None:
            return None
        match _parse_number(self.option, value):
            case ParseResult(value=num):
                if self.start is not None and num < self.start:
                    return ParseError(
                        f"Option {self.option} value must be at least "
                        f"{self.start}, got: {value!r}"
                    )
                if self.stop is not None and num > self.stop:
                    return ParseError(
                        f"Option {self.option} value must be at most "
                        f"{self.stop}, got: {value!r}"
                    )
                return ParseResult(num)
            case ParseError() as err:
                return err

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        if not value and self._is_none_capable:
            return ParseResult(None)
        return super().parse_query_value(value)

    def strategy(self) -> st.SearchStrategy:
        from hypothesis import strategies as st

        if self.start is not None or self.stop is not None:
            numbers = st.floats(
                min_value=None if self.start is None else float(self.start),
                max_value=None if self.stop is None else float(self.stop),
                allow_nan=False,
                allow_infinity=False,
            )
        else:
            numbers = st.integers() | st.floats(allow_nan=False, allow_infinity=False)
        return st.one_of(st.none(), numbers) if self._is_none_capable else numbers

    def format_usage_parts(self) -> list[str]:
        return [self._usage_with_no_flag(self.metavar)]

    def format_help_lines(self) -> list[str]:
        return [
            self._help_line(show_default=self.default is not None),
            *self._help_no_flag_line(f"Set {self.option} to none"),
        ]

    def format_value(self, value: typing.Any) -> list[str]:
        if value == self.default:
            return []
        if value is None:
            return [self._no_flag] if self._no_flag else []
        return [option_value_token(self.option, _format_number(value))]

    def format_query_value(self, value: typing.Any) -> str | None:
        if value == self.default:
            return None
        if value is None:
            return "" if self._is_none_capable else None
        return _format_number(value)

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
    ) -> RangeControl:
        return cls(
            option=option,
            metavar=metavar,
            help_text=help_text,
            default=_range_default(start=start, stop=stop, value=value, steps=steps),
            start=_range_bound(start, steps, min),
            stop=_range_bound(stop, steps, max),
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
        from hypothesis import strategies as st

        return st.tuples(self._number_strategy(), self._number_strategy()).map(
            lambda pair: sorted(pair)
        )

    def _number_strategy(self) -> st.SearchStrategy[Numeric]:
        from hypothesis import strategies as st

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
        return [option_value_token(self.option, _format_range(value))]

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
class MultiSelectControl(_NoneFlag, ValueControl):
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
        return mo.ui.multiselect(
            options=self.select_opts,
            value=selected_keys,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    @property
    def _has_no_flag(self) -> bool:
        return bool(self.default)

    def allows_repeated_values(self) -> bool:
        return True

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if (none_result := self._parse_none_flag(args, [])) is not None:
            return none_result
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
        raw = _decode_json_list(value)
        if raw is None:
            return ParseError(f"Query parameter for {self.option} must be a JSON list")
        keys: list[str] = []
        for item in raw:
            if not isinstance(item, str) or item not in self.select_opts:
                return ParseError(
                    f"Query parameter for {self.option} must be a list of"
                    f" {list(self.select_opts)!r}, got item: {item!r}"
                )
            keys.append(item)
        return ParseResult([self.select_opts[item] for item in keys])

    def strategy(self) -> st.SearchStrategy:
        from hypothesis import strategies as st

        if not self.select_opts:
            return st.just([])
        return st.lists(st.sampled_from(list(self.select_opts.values())), unique=True)

    def format_usage_parts(self) -> list[str]:
        values_text = "{" + "|".join(self.select_opts) + "}"
        return [self._usage_with_no_flag(f"{values_text} ...")]

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
        return [line, *self._help_no_flag_line(f"Clear {self.option}")]

    def format_value(self, value: typing.Any) -> list[str]:
        values = list(value)
        if values == self.default:
            return []
        if not values and self._no_flag:
            return [self._no_flag]
        return [option_value_token(self.option, self._key_for(v)) for v in values]

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
        while True:
            response = input(
                f"{self.help_text} (comma-separated){default_display}: "
            ).strip()
            if not response:
                return []
            parts = [p.strip() for p in response.split(",") if p.strip()]
            choices = list(self.select_opts)
            selected = [
                choices[int(part) - 1]
                if part.isdigit() and 1 <= int(part) <= len(choices)
                else part
                for part in parts
            ]
            invalid = [part for part in selected if part not in self.select_opts]
            if invalid:
                print(
                    f"Please choose from {list(self.select_opts)!r}; "
                    f"invalid: {invalid!r}"
                )
                continue
            return [tok for part in selected for tok in (self.option, part)]

    def _key_for(self, value: typing.Any) -> str:
        return _choice_options.option_key(self.select_opts, value)


@dataclasses.dataclass
class DropdownControl(_NoneFlag, InputControl):
    dropdown_opts: dict[str, typing.Any]
    supports_none: bool
    default: str | None
    cli_opts: dict[str, str] = dataclasses.field(default_factory=dict[str, str])

    def __post_init__(self) -> None:
        if not self.cli_opts:
            self.cli_opts = _choice_options.option_cli_keys(self.dropdown_opts)

    def create_marimo_element(
        self,
        value: typing.Any,
        label: str,
        *,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        disabled: bool = False,
    ) -> typing.Any:
        selected_key = (
            None
            if value is None
            else _choice_options.option_key(self.dropdown_opts, value)
        )
        return mo.ui.dropdown(
            options=self.dropdown_opts,
            value=selected_key,
            label=label,
            on_change=on_change,
            disabled=disabled,
            **self.extra_kwargs,
        )

    @property
    def _has_no_flag(self) -> bool:
        return self.supports_none and self.default is not None

    def parse(self, args: _parse.ParsedArgs) -> ParseResult | ParseError | None:
        if (none_result := self._parse_none_flag(args, None)) is not None:
            return none_result
        raw = args.value_for(self.option)
        if raw is None:
            return None
        key = self._key_from_cli(raw)
        if key is None:
            return ParseError(
                f"Option {self.option} must be one of"
                f" {list(self.cli_opts)!r}, got: {raw!r}"
            )
        return ParseResult(key)

    def parse_query_value(self, value: str) -> ParseResult | ParseError:
        if not value and self.supports_none:
            return ParseResult(None)
        key = self._key_from_cli(value)
        if key is None:
            return ParseError(
                f"Query parameter for {self.option} must be one of"
                f" {list(self.cli_opts)!r}, got: {value!r}"
            )
        return ParseResult(key)

    def strategy(self) -> st.SearchStrategy:
        from hypothesis import strategies as st

        return st.sampled_from(
            [None, *self.dropdown_opts.keys()]
            if self.supports_none
            else list(self.dropdown_opts.keys())
        )

    def format_usage_parts(self) -> list[str]:
        return [self._usage_with_no_flag(self._values_text())]

    def _values_text(self) -> str:
        return "{" + "|".join(self.cli_opts) + "}"

    def format_help_lines(self) -> list[str]:
        line = f"  {self.option} {self._values_text()}: {self.help_text}"
        if self.default is not None:
            line += f" (default: {self._key_for_cli(self.default)})"
        return [line, *self._help_no_flag_line(f"Set {self.option} to none")]

    def format_value(self, value: typing.Any) -> list[str]:
        if self._is_default(value):
            return []
        if value is None:
            assert self._no_flag
            return [self._no_flag]
        return [option_value_token(self.option, self._key_for_cli(value))]

    def format_query_value(self, value: typing.Any) -> str | None:
        if self._is_default(value):
            return None
        return self._key_for_cli(value)

    def _is_default(self, value: typing.Any) -> bool:
        return value == self.default or (
            value is not None
            and self.default is not None
            and self._key_for_cli(value) == self._key_for_cli(self.default)
        )

    def prompt_interactive(self, effective_default: typing.Any = _UNSET) -> list[str]:
        d = self.default if effective_default is _UNSET else effective_default
        choices = [*(["none"] if self.supports_none else []), *self.cli_opts]
        for i, v in enumerate(choices, 1):
            print(f"  {i}) {v}")
        default_key = self._key_for_cli(d) if d is not None else "none"
        default_display = f" [{default_key}]"
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
            elif response in self.cli_opts:
                chosen = response
            elif (
                response.lower() == "none"
                and self.supports_none
                and "none" not in self.cli_opts
            ):
                select_none = True
            else:
                print(f"Please choose from: {', '.join(choices)}")
                continue
            if select_none:
                no_flag = self._no_flag
                return [no_flag] if no_flag else []
            return [self.option, chosen]

    def _key_from_cli(self, value: str) -> str | None:
        if value in self.cli_opts:
            return self.cli_opts[value]
        if value in self.dropdown_opts:
            return value
        return None

    def _key_for_cli(self, value: typing.Any) -> str:
        key = next(
            (
                option_key
                for option_key, option_value in self.dropdown_opts.items()
                if option_value == value
            ),
            value,
        )
        return next(
            (cli for cli, option_key in self.cli_opts.items() if option_key == key),
            "" if value is None else str(value),
        )


def _parse_number(option: str, value: str) -> ParseResult | ParseError:
    # Parse integer-looking strings as int first: routing them through float()
    # would silently lose precision past 2**53 (e.g. "9007199254740993").
    with contextlib.suppress(ValueError):
        return ParseResult(int(value))
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


def _range_bound(
    bound: Numeric | None,
    steps: typing.Sequence[Numeric] | None,
    pick: typing.Callable[[typing.Sequence[Numeric]], Numeric],
) -> Numeric | None:
    """Pick the range bound from explicit steps (via ``min``/``max``) or fall back."""
    return pick(steps) if steps else bound


def _format_range(value: typing.Iterable[typing.Any]) -> str:
    return ",".join(_format_number(v) for v in value)


def format_cli_value(value: typing.Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_number(value: typing.Any) -> str:
    return format_cli_value(value)
