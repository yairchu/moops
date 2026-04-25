import collections.abc as abc
import dataclasses
import math
import marimo as mo
import sys
import typing

help_flags = ["--help", "-h"]


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        if cli_args is None:
            cli_args = sys.argv
        [self._command, *args] = cli_args
        if not self._command:
            self._command = "script"

        self._parse_args(args)
        self.is_help = any(x in self._parsed_args for x in help_flags)

        self._validation_errors: dict[str, str] = {}
        self._control_meta: dict[int, _ControlMeta] = {}

    def _parse_args(self, args: list[str]) -> None:
        """Parse command line arguments into flags and options."""

        self._parsed_args: dict[str, str | None] = {}
        self._unexpected_args: list[str] = []
        prev = None
        for arg in args:
            if arg.startswith("-"):
                if "=" in arg:
                    prefix, value = arg.split("=", 1)
                    self._parsed_args[prefix] = value
                    prev = None
                else:
                    self._parsed_args[arg] = None
            elif prev is not None and prev.startswith("-"):
                self._parsed_args[prev] = arg
            else:
                self._unexpected_args.append(arg)
            prev = arg

    def help(self, *controls) -> mo.Html | None:
        """
        group.help() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        registry = _ControlRegistry(controls, self._control_meta)

        show_help = self.is_help
        if not mo.running_in_notebook():
            issues = list(self._validate_args(registry))
            if issues:
                print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
                print()
                show_help = True

        help_text = registry.format_help(self._command)
        if mo.running_in_notebook():
            return mo.md(f"```\n{help_text}\n```")
        elif show_help:
            print(help_text)
            sys.exit(1)

    def _validate_args(self, registry: "_ControlRegistry") -> abc.Iterator[str]:
        yield from self._validation_errors.values()
        unexp_text = "Unexpected argument: "
        for x in self._unexpected_args:
            yield f"{unexp_text}{x}"
        for k, v in self._parsed_args.items():
            if k in registry.flags:
                if v is not None:
                    yield f"{unexp_text}{v}"
            elif k in registry.str_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in help_flags:
                yield f"{unexp_text}{k}"

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if self.is_help:
            return
        if mo.running_in_notebook():
            return mo.md(text)
        text = text.strip()
        if text.startswith("```\n") and text.endswith("\n```"):
            text = text[4:-4]
        elif text.startswith("`") and text.endswith("`"):
            text = text[1:-1]
        print(f"{text}\n")

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

        opt = _OptionLabel.make(
            label=label, option=flag, prefix="no-" if value else None
        )
        if opt.option in self._parsed_args:
            value = not value
        result = mo.ui.switch(value=value, label=opt.label, **kwargs)
        self._control_meta[id(result)] = _ControlMeta(opt=opt, info=help_text)
        return result

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

        opt = _OptionLabel.make(label=label, option=option)
        desc = _OptionDesc(
            default=value,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        result = mo.ui.text(
            value=self._parsed_args.get(opt.option) or "", label=opt.label, **kwargs
        )
        self._control_meta[id(result)] = _ControlMeta(opt=opt, info=desc)
        return result

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

        opt, value, desc = self._numeric_option(start, value, option, help_text, label)
        result = mo.ui.number(
            start=start, stop=stop, step=step, value=value, label=opt.label, **kwargs
        )
        self._control_meta[id(result)] = _ControlMeta(opt=opt, info=desc)
        return result

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

        opt, value, desc = self._numeric_option(start, value, option, help_text, label)
        result = mo.ui.slider(
            start=start, stop=stop, step=step, value=value, label=opt.label, **kwargs
        )
        self._control_meta[id(result)] = _ControlMeta(opt=opt, info=desc)
        return result

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
        opt = _OptionLabel.make(label=label, option=option)
        keys = list(options)
        if value is None and not allow_select_none:
            value, *_ = keys
        desc = _OptionDesc(
            default=value,
            metavar="{" + "|".join(keys) + "}",
            help_text=help_text,
        )
        raw = self._parsed_args.get(opt.option)
        if raw is not None:
            if raw not in keys:
                self._validation_errors[opt.option] = (
                    f"Option {opt.option} must be one of {keys!r}, got: {raw!r}"
                )
            else:
                value = raw
        result = mo.ui.dropdown(
            options=options,
            value=value,
            label=opt.label,
            allow_select_none=allow_select_none,
            **kwargs,
        )
        self._control_meta[id(result)] = _ControlMeta(opt=opt, info=desc)
        return result

    def _numeric_option(
        self,
        start: float,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
    ) -> tuple["_OptionLabel", float, "_OptionDesc"]:
        """Parse a numeric CLI option, returning (opt, resolved_value, desc)."""

        if value is None:
            value = start
        opt = _OptionLabel.make(label=label, option=option)
        desc = _OptionDesc(
            default=str(value),
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        raw = self._parsed_args.get(opt.option)
        if raw is not None:
            try:
                value = float(raw)
            except ValueError:
                self._validation_errors[opt.option] = (
                    f"Option {opt.option} expects a number, got: {raw!r}"
                )
            else:
                if math.isfinite(value) and value == int(value):
                    value = int(value)
        return opt, value, desc


@dataclasses.dataclass
class _OptionDesc:
    """Metadata for CLI options with defaults and help text."""

    default: str | None
    metavar: str
    help_text: str | None


@dataclasses.dataclass
class _OptionLabel:
    """Maps between UI labels and CLI option names."""

    label: str
    option: str

    @staticmethod
    def make(
        label: str | None, option: str | None, prefix: str | None = None
    ) -> "_OptionLabel":
        """Generate OptionLabel from label or option name."""

        if option is None:
            assert label is not None
            option = f"--{prefix or ''}{label.lower().replace(' ', '-')}"
        else:
            assert prefix is None
            if label is None:
                label = option.replace("-", " ")
        return _OptionLabel(label=label, option=option)


@dataclasses.dataclass
class _ControlMeta:
    opt: _OptionLabel
    info: str | _OptionDesc


class _ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(self, controls: tuple, control_meta: dict[int, _ControlMeta]) -> None:
        self.flags: dict[str, str] = {}
        self.str_options: dict[str, _OptionDesc] = {}
        seen: set[str] = set()
        for ctrl in controls:
            meta = control_meta.get(id(ctrl))
            if meta is None:
                raise ValueError(f"Control {ctrl!r} was not created by this Group")
            if meta.opt.option in seen:
                raise ValueError(
                    f"Option {meta.opt.option!r} passed to help() more than once"
                )
            seen.add(meta.opt.option)
            if isinstance(meta.info, str):
                self.flags[meta.opt.option] = meta.info
            else:
                self.str_options[meta.opt.option] = meta.info

    def format_help(self, command: str) -> str:
        segments = [
            f"Usage: {command} {' '.join(f'[{x}]' for x in [*self.flags.keys(), '-h/--help'])}"
        ]
        opts_help = [f"  {k}: {v}" for k, v in self.flags.items()]
        for k, v in self.str_options.items():
            opts_help.append(
                f"  {k} {v.metavar}: {v.help_text}{f' (default: {v.default})' if v.default else ''}"
            )
        if opts_help:
            segments.append("\n".join(opts_help))
        return "\n\n".join(segments)
