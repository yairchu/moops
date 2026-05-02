import dataclasses
import inspect
import pathlib
import sys
import typing

import marimo as mo

from . import _options, _parse, interface


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        self._state = _GroupState(args=_parse.ParsedArgs.parse(cli_args))
        self._overrides: dict[str, typing.Any] = {}
        self._option_prefix: str = ""

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> "Group":
        instance = object.__new__(cls)
        instance._state = _GroupState(args=_parse.ParsedArgs.parse(["run"]))
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
        parent_overrides = self._overrides.get(prefix, {})
        child._overrides = {
            **(parent_overrides if isinstance(parent_overrides, dict) else {}),
            **(overrides or {}),
        }
        child._option_prefix = f"{prefix}-"
        return child

    def interface(self, *controls: typing.Any) -> mo.Html | interface.Interface | None:
        """
        group.interface() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).

        Controls NOT passed here are notebook-only: they won't appear in CLI
        help or be validated as CLI arguments, but they remain overridable via
        moops.run() and visible to moops.testing.from_notebook().
        """

        return (
            interface.Interface(
                controls,
                notebook_name=pathlib.Path(inspect.stack()[1].filename).name,
                option_prefix=self._option_prefix,
            )
            if self._option_prefix
            else self._state.interface(controls)
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
        if opt.option in self._state.args.options:
            value = not value
        return self._register(
            mo.ui.switch(
                value=self._get_override(opt, value),
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                opt=opt, info=help_text, overridden=self._is_overridden(opt)
            ),
        )

    def _register(self, control: typing.Any, meta: _options.ControlMeta) -> typing.Any:
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
        **kwargs: typing.Any,
    ) -> mo.ui.text:
        """Create a text input UI element that maps to a CLI option."""

        opt, value, desc = self._text_option(
            value, placeholder, option, help_text, label
        )
        return self._register(
            mo.ui.text(
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                opt=opt, info=desc, overridden=self._is_overridden(opt)
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

        opt, value, desc = self._text_option(
            value, placeholder, option, help_text, label
        )
        stdin_flag = None if self._is_overridden(opt) else f"{opt.option}-from-stdin"
        if stdin_flag:
            match self._state.args.get_text_area(opt.option, stdin_flag):
                case _parse.ParseError(message=msg):
                    self._state.validation_errors[opt.option] = msg
                case str() as v:
                    value = v
                case _:
                    pass
        return self._register(
            mo.ui.text_area(
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt),
                **kwargs,
            ),
            _options.ControlMeta(
                opt=opt,
                info=desc,
                stdin_flag=stdin_flag,
                overridden=self._is_overridden(opt),
            ),
        )

    def _text_option(
        self,
        value: str,
        placeholder: str,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[_options.OptionLabel, str, _options.OptionDesc]:
        """Parse a string CLI option."""

        opt = self._make_opt(label=label, option=option)
        desc = _options.OptionDesc(
            default=value,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        raw = self._state.args.options.get(opt.option)
        return opt, self._get_override(opt, value if raw is None else raw), desc

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

        value, meta = self._numeric_option(start, value, option, help_text, label)
        return self._register(
            mo.ui.number(
                start=start,
                value=value,
                label=meta.opt.label,
                disabled=self._is_overridden(meta.opt),
                **kwargs,
            ),
            meta,
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

        value, meta = self._numeric_option(start, value, option, help_text, label)
        return self._register(
            mo.ui.slider(
                start=start,
                value=value,
                label=meta.opt.label,
                disabled=self._is_overridden(meta.opt),
                **kwargs,
            ),
            meta,
        )

    def _numeric_option(
        self,
        start: float | None,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple[float, _options.ControlMeta]:
        """Parse a numeric CLI option."""

        if value is None:
            value = start
        opt = self._make_opt(label=label, option=option)
        desc = _options.OptionDesc(
            default=str(value),
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        parsed = self._state.args.get_num(opt.option)
        if isinstance(parsed, _parse.ParseError):
            if not self._is_overridden(opt):
                self._state.validation_errors[opt.option] = parsed.message
        elif parsed is not None:
            value = parsed
        return (
            self._get_override(opt, value),
            _options.ControlMeta(
                opt=opt, info=desc, overridden=self._is_overridden(opt)
            ),
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
        **kwargs: typing.Any,
    ) -> mo.ui.dropdown:
        """Create a dropdown UI element that maps to a CLI option."""

        assert len(options) > 0, "Dropdown options cannot be empty"
        opt = self._make_opt(label=label, option=option)
        keys = list(options)
        if value is None and not allow_select_none:
            value, *_ = keys
        desc = _options.OptionDesc(
            default=value,
            metavar="{" + "|".join(keys) + "}",
            allowed_values=keys,
            help_text=help_text,
        )
        no_flag = (
            f"--no-{opt.option.lstrip('-')}"
            if allow_select_none and value is not None
            else None
        )
        override = self._get_override(opt, None)
        if override is None:
            match self._state.args.get_dropdown(opt.option, keys, no_flag):
                case _parse.ParseError(message=msg):
                    self._state.validation_errors[opt.option] = msg
                case _parse.DropdownValue(value=v):
                    value = v
                case _:
                    pass
        else:
            # mo.ui.dropdown doesn't support disabled; filter to one option as a
            # workaround so the user can't change the value. Remove once marimo adds
            # disabled support for dropdowns.
            options = (
                {override: options[override]}
                if isinstance(options, dict)
                else [override]
            )
        return self._register(
            mo.ui.dropdown(
                options=options,
                value=self._get_override(opt, value),
                label=opt.label,
                allow_select_none=allow_select_none,
                **kwargs,
            ),
            _options.ControlMeta(
                opt=opt, info=desc, no_flag=no_flag, overridden=self._is_overridden(opt)
            ),
        )

    def _override_key(self, opt: _options.OptionLabel) -> str:
        return opt.label.lower().replace(" ", "_")

    def _get_override(
        self, opt: _options.OptionLabel, default: typing.Any
    ) -> typing.Any:
        return self._overrides.get(self._override_key(opt), default)

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


@dataclasses.dataclass
class _GroupState:
    args: _parse.ParsedArgs
    validation_errors: dict[str, str] = dataclasses.field(default_factory=lambda: {})
    control_meta: dict[int, _options.ControlMeta] = dataclasses.field(
        default_factory=lambda: {}
    )

    def interface(self, controls: tuple[typing.Any]) -> mo.Html | None:
        registry = _options.ControlRegistry(controls, self.control_meta)

        show_help = self.args.is_help
        has_errors = False
        if not mo.running_in_notebook():
            issues = list(registry.validate(self.args, self.validation_errors))
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

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if mo.running_in_notebook():
            return mo.md(text)
        if self.args.is_help:
            return None
        text = text.strip()
        if text.startswith("```\n") and text.endswith("\n```"):
            text = text[4:-4]
        elif text.startswith("`") and text.endswith("`"):
            text = text[1:-1]
        print(f"{text}\n")
