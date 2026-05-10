import inspect
import pathlib
import shlex
import typing
import warnings

import marimo as mo

from . import _cli_map, _naming, _options, _parse, _query_params, interface
from .presets import Presets

Numeric = int | float


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(
        self,
        cli_args: list[str] | None = None,
        presets: Presets | None = None,
    ) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        self.option: str = ""
        command, rest = _parse.split_argv(cli_args)
        self._command = command
        self._state = _parse.ParseState(args=_parse.ParsedArgs.from_options(rest))
        self._cli_map = _cli_map.CliMap()
        self._overrides: dict[str, typing.Any] = {}
        self._presets = presets
        self._preset_state = self._build_preset_state()
        self._query_params = _query_params.QueryParams.from_notebook()

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> "Group":
        instance = cls(["run"])
        instance._overrides = overrides
        return instance

    def subgroup(
        self,
        prefix: str,
        overrides: dict[str, typing.Any] | None = None,
        presets: Presets | None = None,
    ) -> "Group":
        """Create a child Group that prefixes all its option names with '{prefix}-'.

        Pass a nested dict under the same key to moops.run() to override controls
        in this subgroup: moops.run(notebook, casing={"style": "snake_case"}).
        Explicit overrides take precedence over those passed via moops.run().

        Pass `presets=` to give the subgroup its own preset selector; otherwise
        it inherits the parent's preset state.
        """
        child = type(self)([prefix])
        child._state = self._state
        child._cli_map = _cli_map.CliMap()
        child._overrides = {**self._overrides.get(prefix, {}), **(overrides or {})}
        child.option = f"{self.option}-{prefix}" if self.option else f"--{prefix}"
        child._presets = presets
        child._preset_state = (
            child._build_preset_state() if presets else self._preset_state
        )
        child._query_params = self._query_params.subgroup(prefix)
        return child

    def _build_preset_state(self) -> _parse.ParseState | None:
        if self._presets is None or not self._presets.selected_args:
            return None
        args = _parse.ParsedArgs.from_options(shlex.split(self._presets.selected_args))
        return _parse.ParseState(args=args)

    def interface(self, *controls: typing.Any) -> interface.Interface:
        """
        group.interface() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        iface = interface.Interface(
            controls,
            cli_map=self._cli_map,
            overrides=self._overrides,
            notebook_name=pathlib.Path(inspect.stack()[1].filename).name,
            option_prefix=self.option,
            presets=self._presets,
            command=self._command,
        )
        if self.option or not mo.running_in_notebook():
            missing_options = iface.missing_options()
            if missing_options:
                warnings.warn(
                    f"Controls registered with this Group "
                    f"but not passed to interface(): {', '.join(missing_options)}",
                    stacklevel=2,
                )
        if not self.option and not mo.running_in_notebook():
            iface.validate_or_exit(self._state)
        return iface

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if mo.running_in_notebook():
            return mo.md(text)
        if self._state.args.is_help:
            return None
        text = text.strip()
        if text.startswith("```\n") and text.endswith("\n```"):
            text = text[4:-4]
        elif text.startswith("`") and text.endswith("`"):
            text = text[1:-1]
        print(f"{text}\n")
        return None

    def switch(
        self,
        value: bool = False,
        flag: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[bool], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.switch:
        """Create a switch UI element that maps to a CLI flag."""

        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        cli = _options.FlagControl(
            option=opt.option, help_text=help_text, default=value
        )
        return self._cli_map.register(
            mo.ui.switch(
                value=self._get_value(cli, value),
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def checkbox(
        self,
        value: bool = False,
        flag: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[bool], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.checkbox:
        """Create a checkbox UI element that maps to a CLI flag."""

        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        cli = _options.FlagControl(
            option=opt.option, help_text=help_text, default=value
        )
        return self._cli_map.register(
            mo.ui.checkbox(
                value=self._get_value(cli, value),
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def text(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[str], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.text:
        """Create a text input UI element that maps to a CLI option."""

        opt = self._make_opt(label=label, option=option)
        cli = _options.TextControl(
            option=opt.option,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            default=value,
        )
        return self._cli_map.register(
            mo.ui.text(
                value=self._get_value(cli, value),
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def text_area(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[str], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.text_area:
        """Create a text area UI element that maps to a CLI option."""

        opt = self._make_opt(label=label, option=option)
        cli = _options.TextAreaControl(
            option=opt.option,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            default=value,
        )
        return self._cli_map.register(
            mo.ui.text_area(
                value=self._get_value(cli, value),
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def number(
        self,
        start: float | None = None,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[Numeric | None], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.number:
        """Create a number input UI element that maps to a CLI option."""

        opt, cli, value = self._numeric_cli(start, value, option, help_text, label)
        return self._cli_map.register(
            mo.ui.number(
                start=start,
                value=value,
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def slider(
        self,
        start: float | None = None,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[Numeric | None], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.slider:
        """Create a slider UI element that maps to a CLI option."""

        opt, cli, value = self._numeric_cli(start, value, option, help_text, label)
        return self._cli_map.register(
            mo.ui.slider(
                start=start,
                value=value,
                label=opt.label_with_tooltip(help_text),
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def range_slider(
        self,
        start: Numeric | None = None,
        stop: Numeric | None = None,
        step: Numeric | None = None,
        value: typing.Sequence[Numeric] | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        steps: typing.Sequence[Numeric] | None = None,
        on_change: typing.Callable[[typing.Sequence[Numeric]], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.range_slider:
        """Create a range slider UI element that maps to a CLI option."""

        opt = self._make_opt(label=label, option=option)
        cli = _options.RangeControl.from_slider(
            option=opt.option,
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            start=start,
            stop=stop,
            value=value,
            steps=steps,
        )
        return self._cli_map.register(
            mo.ui.range_slider(
                start=start,
                stop=stop,
                step=step,
                value=self._get_value(cli, cli.default),
                label=opt.label_with_tooltip(help_text),
                steps=steps,
                disabled=self._is_overridden(opt.option),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def _numeric_cli(
        self,
        start: float | None,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[_naming.OptionLabel, _options.NumberControl, float | None]:
        if value is None:
            value = start
        opt = self._make_opt(label=label, option=option)
        cli = _options.NumberControl(
            option=opt.option,
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            default=value,
        )
        return opt, cli, self._get_value(cli, value)

    def dropdown(
        self,
        options: list[str] | dict[str, typing.Any],
        value: str | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        allow_select_none: bool = True,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.dropdown:
        """Create a dropdown UI element that maps to a CLI option."""

        assert len(options) > 0, "Dropdown options cannot be empty"
        opt = self._make_opt(label=label, option=option)
        keys = list(options)
        if value is None and not allow_select_none:
            value, *_ = keys
        cli = _options.DropdownControl(
            option=opt.option,
            allowed_values=keys,
            supports_none=allow_select_none,
            default=value,
            help_text=help_text,
        )
        if self._is_overridden(opt.option):
            # mo.ui.dropdown doesn't support disabled; filter to one option as a
            # workaround so the user can't change the value. Remove once marimo adds
            # disabled support for dropdowns.
            override = self._overrides[self._override_key(opt.option)]
            options = (
                {override: None if override is None else options[override]}
                if isinstance(options, dict)
                else [override]
            )
        return self._cli_map.register(
            mo.ui.dropdown(
                options=options,
                value=self._get_value(cli, value),
                label=opt.label_with_tooltip(help_text),
                allow_select_none=allow_select_none,
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def _override_key(self, option: str) -> str:
        option = option[len(self.option) :].lstrip("-")
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def _get_value(
        self,
        control: _options.CliControl,
        default: typing.Any,
    ) -> typing.Any:
        key = self._override_key(control.option)
        if key in self._overrides:
            return self._overrides[key]
        if self._preset_state is not None:
            match control.parse(self._preset_state.args):
                case _options.ParseResult(value=v):
                    self._sync_query_param(control, v, key)
                    return v
                case None:
                    self._sync_query_param(control, default, key)
                    return default
                case _:
                    pass
        raw = self._query_params.get(key)
        if raw is not None:
            match control.parse_query_value(raw):
                case _options.ParseError(message=msg):
                    self._state.validation_errors[control.option] = msg
                case _options.ParseResult(value=v):
                    return v
        val = default
        match control.parse(self._state.args):
            case _options.ParseError(message=msg):
                self._state.validation_errors[control.option] = msg
            case _options.ParseResult(value=v):
                val = v
            case None:
                pass
        return val

    def _is_overridden(self, option: str) -> bool:
        return self._override_key(option) in self._overrides

    def _query_on_change(
        self,
        control: _options.CliControl,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> typing.Callable[[typing.Any], None] | None:
        return self._query_params.on_change(
            control,
            self._override_key(control.option),
            on_change,
            disabled=self._is_overridden(control.option),
        )

    def _sync_query_param(
        self,
        control: _options.CliControl,
        value: typing.Any,
        key: str,
    ) -> None:
        self._query_params.sync(control, key, value)

    def _make_opt(
        self, label: str | None, option: str | None, prefix: str | None = None
    ) -> _naming.OptionLabel:
        opt = _naming.OptionLabel.make(label=label, option=option, prefix=prefix)
        if self.option:
            opt = _naming.OptionLabel(
                label=opt.label,
                option=f"{self.option}-{opt.option.lstrip('-')}",
            )
        return opt
