import inspect
import pathlib
import typing

import marimo as mo

from . import _options, _parse, _state, interface


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        self._state = _state.GroupState(args=_parse.ParsedArgs.parse(cli_args))
        self._overrides: dict[str, typing.Any] = {}
        self._option_prefix: str = ""

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> "Group":
        instance = object.__new__(cls)
        instance._state = _state.GroupState(args=_parse.ParsedArgs.parse(["run"]))
        instance._overrides = overrides
        instance._option_prefix = ""
        return instance

    def subgroup(
        self, prefix: str, overrides: dict[str, typing.Any] | None = None
    ) -> "Group":
        """Create a child Group that prefixes all its option names with '{prefix}-'.

        Pass a nested dict under the same key to moops.run() to override controls
        in this subgroup: moops.run(notebook, casing={"style": "snake_case"}).
        Explicit overrides take precedence over those passed via moops.run().
        """
        child = object.__new__(Group)
        child._state = self._state
        child._overrides = {**self._overrides.get(prefix, {}), **(overrides or {})}
        child._option_prefix = f"{prefix}-"
        return child

    def interface(self, *controls: typing.Any) -> mo.Html | interface.Interface | None:
        """
        group.interface() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        return (
            interface.Interface(
                controls,
                notebook_name=pathlib.Path(inspect.stack()[1].filename).name,
                option_prefix=self._option_prefix,
            )
            if self._option_prefix
            else self._state.interface_info(controls)
        )

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        return self._state.md(text)

    def switch(
        self,
        value: bool = False,
        flag: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.switch:
        """Create a switch UI element that maps to a CLI flag."""

        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        cli = _options.FlagControl(
            option=opt.option, help_text=help_text, default=value
        )
        return self._state.register(
            mo.ui.switch(
                value=self._get_value(opt, cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt),
                option_prefix=self._option_prefix,
            ),
        )

    def text(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
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
        return self._state.register(
            mo.ui.text(
                value=self._get_value(opt, cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt),
                option_prefix=self._option_prefix,
            ),
        )

    def text_area(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
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
        return self._state.register(
            mo.ui.text_area(
                value=self._get_value(opt, cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt),
                option_prefix=self._option_prefix,
            ),
        )

    def number(
        self,
        start: float | None = None,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.number:
        """Create a number input UI element that maps to a CLI option."""

        opt, cli, value = self._numeric_cli(start, value, option, help_text, label)
        return self._state.register(
            mo.ui.number(
                start=start,
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(cli=cli, overridden=self._is_overridden(opt)),
        )

    def slider(
        self,
        start: float | None = None,
        value: float | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.slider:
        """Create a slider UI element that maps to a CLI option."""

        opt, cli, value = self._numeric_cli(start, value, option, help_text, label)
        return self._state.register(
            mo.ui.slider(
                start=start,
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(cli=cli, overridden=self._is_overridden(opt)),
        )

    def _numeric_cli(
        self,
        start: float | None,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[_options.OptionLabel, _options.NumberControl, float | None]:
        if value is None:
            value = start
        opt = self._make_opt(label=label, option=option)
        cli = _options.NumberControl(
            option=opt.option,
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            default=value,
        )
        return opt, cli, self._get_value(opt, cli, value)

    def dropdown(
        self,
        options: list[str] | dict[str, typing.Any],
        value: str | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        allow_select_none: bool = True,
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
        if self._is_overridden(opt):
            # mo.ui.dropdown doesn't support disabled; filter to one option as a
            # workaround so the user can't change the value. Remove once marimo adds
            # disabled support for dropdowns.
            override = self._overrides[self._override_key(opt)]
            options = (
                {override: options[override]}
                if isinstance(options, dict)
                else [override]
            )
        return self._state.register(
            mo.ui.dropdown(
                options=options,
                value=self._get_value(opt, cli, value),
                label=opt.label,
                allow_select_none=allow_select_none,
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt),
                option_prefix=self._option_prefix,
            ),
        )

    def _override_key(self, opt: _options.OptionLabel) -> str:
        option = opt.option.lstrip("-")
        if self._option_prefix:
            option = option[len(self._option_prefix) :]
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def _get_value(
        self,
        opt: _options.OptionLabel,
        control: _options.CliControl,
        default: typing.Any,
    ) -> typing.Any:
        key = self._override_key(opt)
        if key in self._overrides:
            return self._overrides[key]
        val = default
        match control.parse(self._state.args):
            case _options.ParseError(message=msg):
                self._state.validation_errors[opt.option] = msg
            case _options.ParseResult(value=v):
                val = v
            case None:
                pass
        return val

    def _is_overridden(self, opt: _options.OptionLabel) -> bool:
        return self._override_key(opt) in self._overrides

    def _make_opt(
        self, label: str | None, option: str | None, prefix: str | None = None
    ) -> _options.OptionLabel:
        opt = _options.OptionLabel.make(label=label, option=option, prefix=prefix)
        if self._option_prefix:
            opt = _options.OptionLabel(
                label=opt.label,
                option=f"--{self._option_prefix}{opt.option.lstrip('-')}",
            )
        return opt
