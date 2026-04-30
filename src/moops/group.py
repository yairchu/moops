import dataclasses
import itertools
import marimo as mo
import sys
import typing

from . import _cli, _options, _output


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        self._state = _GroupState(
            args=_cli._ParsedArgs.parse(sys.argv if cli_args is None else cli_args)
        )
        self._overrides: dict[str, typing.Any] = {}
        self._option_prefix: str = ""

    def subgroup(
        self, prefix: str, overrides: dict[str, typing.Any] | None = None
    ) -> "Group":
        """Create a child Group that prefixes all its option names with '{prefix}-'."""
        child = object.__new__(Group)
        child._state = self._state
        child._overrides = overrides or {}
        child._option_prefix = f"{prefix}-"
        return child

    def render_cli(self, *controls) -> mo.Html | _cli._CliBundle | None:
        """
        group.render_cli() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        if self._option_prefix:
            return _cli._CliBundle(controls)
        return self._state.render_cli(
            tuple(
                c
                for x in controls
                for c in (x.controls if isinstance(x, _cli._CliBundle) else (x,))
            )
        )

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        return None if self._state.args.is_help else _output._md(text)

    def switch(
        self,
        value: bool = False,
        flag: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.switch:
        """Create a switch UI element that maps to a CLI flag."""

        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        if opt.option in self._state.args.options:
            value = not value
        return self._register(
            mo.ui.switch(
                value=self._get_override(opt, value), label=opt.label, **kwargs
            ),
            _options._ControlMeta(opt=opt, info=help_text),
        )

    def _register(self, control, meta: _options._ControlMeta):
        self._state.control_meta[id(control)] = meta
        return control

    def text(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.text:
        """Create a text input UI element that maps to a CLI option."""

        opt, value, desc = self._text_option(
            value, placeholder, option, help_text, label
        )
        return self._register(
            mo.ui.text(value=value, label=opt.label, **kwargs),
            _options._ControlMeta(opt=opt, info=desc),
        )

    def text_area(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.text_area:
        """Create a text area UI element that maps to a CLI option."""

        opt, value, desc = self._text_option(
            value, placeholder, option, help_text, label
        )
        if self._get_override(opt, None) is not None:
            stdin_flag = None
        else:
            stdin_flag = f"{opt.option}-from-stdin"
            if not mo.running_in_notebook() and stdin_flag in self._state.args.options:
                if opt.option in self._state.args.options:
                    self._state.validation_errors[opt.option] = [
                        f"Cannot use both {opt.option} and {stdin_flag}"
                    ]
                elif self._state.args.options[stdin_flag] is None:
                    value = sys.stdin.read()
        return self._register(
            mo.ui.text_area(value=value, label=opt.label, **kwargs),
            _options._ControlMeta(opt=opt, info=desc, stdin_flag=stdin_flag),
        )

    def _text_option(
        self,
        value: str,
        placeholder: str,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[_options._OptionLabel, str, _options._OptionDesc]:
        """Parse a string CLI option."""

        opt = self._make_opt(label=label, option=option)
        desc = _options._OptionDesc(
            default=value,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        raw = self._state.args.options.get(opt.option)
        return opt, self._get_override(opt, value if raw is None else raw), desc

    def number(
        self,
        start: float = 0,
        stop: float = 100,
        step: float = 1,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.number:
        """Create a number input UI element that maps to a CLI option."""

        opt, value, meta = self._numeric_option(start, value, option, help_text, label)
        return self._register(
            mo.ui.number(
                start=start,
                stop=stop,
                step=step,
                value=value,
                label=opt.label,
                **kwargs,
            ),
            meta,
        )

    def slider(
        self,
        start: float = 0,
        stop: float = 100,
        step: float = 1,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.slider:
        """Create a slider UI element that maps to a CLI option."""

        opt, value, meta = self._numeric_option(start, value, option, help_text, label)
        return self._register(
            mo.ui.slider(
                start=start,
                stop=stop,
                step=step,
                value=value,
                label=opt.label,
                **kwargs,
            ),
            meta,
        )

    def _numeric_option(
        self,
        start: float,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[_options._OptionLabel, float, _options._ControlMeta]:
        """Parse a numeric CLI option."""

        if value is None:
            value = start
        opt = self._make_opt(label=label, option=option)
        desc = _options._OptionDesc(
            default=str(value),
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        parsed = self._state.args.get_num(opt.option)
        if isinstance(parsed, str):
            if self._get_override(opt, None) is None:
                self._state.validation_errors[opt.option] = [parsed]
        elif parsed is not None:
            value = parsed
        return (
            opt,
            self._get_override(opt, value),
            _options._ControlMeta(opt=opt, info=desc),
        )

    def dropdown(
        self,
        options: list[str] | dict[str, typing.Any],
        value: str | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        allow_select_none: bool = True,
        **kwargs,
    ) -> mo.ui.dropdown:
        """Create a dropdown UI element that maps to a CLI option."""

        assert len(options) > 0, "Dropdown options cannot be empty"
        opt = self._make_opt(label=label, option=option)
        keys = list(options)
        if value is None and not allow_select_none:
            value, *_ = keys
        desc = _options._OptionDesc(
            default=value,
            metavar="{" + "|".join(keys) + "}",
            help_text=help_text,
        )
        if self._get_override(opt, None) is None:
            raw = self._state.args.options.get(opt.option)
            if raw is not None:
                if raw not in keys:
                    self._state.validation_errors[opt.option] = [
                        f"Option {opt.option} must be one of {keys!r}, got: {raw!r}"
                    ]
                else:
                    value = raw
        return self._register(
            mo.ui.dropdown(
                options=options,
                value=self._get_override(opt, value),
                label=opt.label,
                allow_select_none=allow_select_none,
                **kwargs,
            ),
            _options._ControlMeta(opt=opt, info=desc),
        )

    def _get_override(
        self, opt: _options._OptionLabel, default: typing.Any
    ) -> typing.Any:
        return self._overrides.get(opt.label.lower().replace(" ", "_"), default)

    def _make_opt(
        self, label: str | None, option: str | None, prefix: str | None = None
    ) -> _options._OptionLabel:
        opt = _options._OptionLabel.make(label=label, option=option, prefix=prefix)
        if self._option_prefix:
            opt = _options._OptionLabel(
                label=opt.label,
                option=f"--{self._option_prefix}{opt.option.lstrip('-')}",
            )
        return opt


@dataclasses.dataclass
class _GroupState:
    args: _cli._ParsedArgs
    validation_errors: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    control_meta: dict[int, _options._ControlMeta] = dataclasses.field(
        default_factory=dict
    )

    def render_cli(self, controls: tuple) -> mo.Html | None:
        registry = _options._ControlRegistry(controls, self.control_meta)

        show_help = self.args.is_help
        has_errors = False
        if not mo.running_in_notebook():
            issues = [
                *itertools.chain.from_iterable(self.validation_errors.values()),
                *registry.validate(self.args),
            ]
            if issues:
                print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
                print()
                show_help = True
                has_errors = True

        help_text = registry.format_help(self.args.command)
        if mo.running_in_notebook():
            return mo.md(
                f"This notebook also works as a script:\n```\n{help_text.strip()}\n```"
            )
        elif show_help:
            print(help_text)
            sys.exit(1 if has_errors else 0)
        return None
