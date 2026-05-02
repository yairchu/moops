import inspect
import pathlib
import sys
import typing
import warnings
import weakref

import marimo as mo
from hypothesis import strategies as st

from . import _naming, _options, _parse, _registry, interface


class Group(_options.CliControl):
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        self.option: str = ""
        self.help_text: str = ""
        self._args: _parse.ParsedArgs = _parse.ParsedArgs.parse(cli_args)
        self._validation_errors: dict[str, str] = {}
        self._overrides: dict[str, typing.Any] = {}
        self._control_meta: dict[int, _options.ControlMeta] = {}

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> "Group":
        instance = cls(["run"])
        instance._overrides = overrides
        return instance

    def subgroup(
        self, prefix: str, overrides: dict[str, typing.Any] | None = None
    ) -> "Group":
        """Create a child Group that prefixes all its option names with '{prefix}-'.

        Pass a nested dict under the same key to moops.run() to override controls
        in this subgroup: moops.run(notebook, casing={"style": "snake_case"}).
        Explicit overrides take precedence over those passed via moops.run().
        """
        child = type(self)([prefix])
        child._args = self._args
        child._validation_errors = self._validation_errors
        child._overrides = {**self._overrides.get(prefix, {}), **(overrides or {})}
        child.option = f"{self.option}-{prefix}" if self.option else f"--{prefix}"
        return self._register(child, _options.ControlMeta(cli=child, overridden=False))

    def interface(self, *controls: typing.Any) -> mo.Html | interface.Interface | None:
        """
        group.interface() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        missing_options = self._missing_from_interface(controls)
        if self.option:
            if missing_options:
                warnings.warn(
                    f"Controls registered with this Group "
                    f"but not passed to interface(): {', '.join(missing_options)}",
                    stacklevel=2,
                )
            return interface.Interface(
                controls,
                self._control_meta,
                notebook_name=pathlib.Path(inspect.stack()[1].filename).name,
                option_prefix=self.option,
            )

        registry = _registry.ControlRegistry(controls, self._control_meta)
        if mo.running_in_notebook():
            return mo.md(
                f"This notebook also works as a script:\n```\n{self._help()}\n```\n\n"
            )

        issues = list(registry.validate(self._args, self._validation_errors))
        if issues:
            print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
            print()

        if self._args.is_help or issues:
            print(self._help())
            sys.exit(1 if issues else 0)
        return None

    def _missing_from_interface(self, controls: tuple[typing.Any]) -> list[str]:
        interface_ids = {id(ctrl) for ctrl in controls}
        return [
            meta.cli.option
            for ctrl_id, meta in self._control_meta.items()
            if meta.control_ref is not None
            and meta.control_ref() is not None
            and ctrl_id not in interface_ids
        ]

    def _help(self) -> str:
        usage_parts = self.format_usage_parts()
        usage_parts.append("[-h/--help]")
        segments = [
            f"Usage: {self._args.command.rsplit('/', 1)[-1]} {' '.join(usage_parts)}"
        ]
        help_lines = self.format_help_lines()
        if help_lines:
            segments.append("\n".join(help_lines))
        return "\n\n".join(segments)

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if mo.running_in_notebook():
            return mo.md(text)
        if self._args.is_help:
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
        **kwargs: typing.Any,
    ) -> mo.ui.switch:
        """Create a switch UI element that maps to a CLI flag."""

        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        cli = _options.FlagControl(
            option=opt.option, help_text=help_text, default=value
        )
        return self._register(
            mo.ui.switch(
                value=self._get_value(cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt.option),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt.option),
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
        return self._register(
            mo.ui.text(
                value=self._get_value(cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt.option),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt.option),
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
        return self._register(
            mo.ui.text_area(
                value=self._get_value(cli, value),
                label=opt.label,
                disabled=self._is_overridden(opt.option),
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt.option),
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
        return self._register(
            mo.ui.number(
                start=start,
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt.option),
                **kwargs,
            ),
            _options.ControlMeta(cli=cli, overridden=self._is_overridden(opt.option)),
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
        return self._register(
            mo.ui.slider(
                start=start,
                value=value,
                label=opt.label,
                disabled=self._is_overridden(opt.option),
                **kwargs,
            ),
            _options.ControlMeta(cli=cli, overridden=self._is_overridden(opt.option)),
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
        return self._register(
            mo.ui.dropdown(
                options=options,
                value=self._get_value(cli, value),
                label=opt.label,
                allow_select_none=allow_select_none,
                **kwargs,
            ),
            _options.ControlMeta(
                cli=cli,
                overridden=self._is_overridden(opt.option),
            ),
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
        val = default
        match control.parse(self._args):
            case _options.ParseError(message=msg):
                self._validation_errors[control.option] = msg
            case _options.ParseResult(value=v):
                val = v
            case None:
                pass
        return val

    def _is_overridden(self, option: str) -> bool:
        return self._override_key(option) in self._overrides

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

    def _register(self, control: typing.Any, meta: _options.ControlMeta) -> typing.Any:
        meta.control_ref = weakref.ref(control)
        self._control_meta[id(control)] = meta
        return control

    def _controls(self) -> dict[str, _options.CliControl]:
        result: dict[str, _options.CliControl] = {}
        for meta in self._control_meta.values():
            if meta.control_ref is None:
                continue
            control = meta.control_ref()
            if control is None:
                continue
            key = self._override_key(meta.cli.option)
            if key in self._overrides:
                continue
            result[key] = meta.cli
        return result

    def parse(
        self, args: _parse.ParsedArgs
    ) -> _options.ParseResult | _options.ParseError | None:
        result = {}
        for k, v in self._controls().items():
            match v.parse(args):
                case _options.ParseError() as e:
                    return e
                case _options.ParseResult(value=v):
                    result[k] = v
                case None:
                    pass
        return _options.ParseResult(result)

    def strategy(self) -> st.SearchStrategy:
        return st.fixed_dictionaries(
            {k: v.strategy() for k, v in self._controls().items()}
        )

    def format_usage_parts(self) -> list[str]:
        parts: list[str] = []
        for v in self._controls().values():
            parts.extend(v.format_usage_parts())
        return parts

    def format_help_lines(self) -> list[str]:
        lines: list[str] = []
        for v in self._controls().values():
            lines.extend(v.format_help_lines())
        return lines

    @property
    def default(self) -> dict[str, typing.Any]:
        return {
            k: v.default  # type: ignore
            for k, v in self._controls().items()
            if hasattr(v, "default")
        }
