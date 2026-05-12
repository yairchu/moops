from __future__ import annotations

import inspect
import pathlib
import shlex
import sys
import typing
import warnings
import weakref

import marimo as mo

from . import _input_map, _naming, _options, _parse, _query_params, interface
from .interface import FileBrowserWithInitialSelection
from .presets import Presets

Numeric = int | float


def _demote_markdown_headings(text: str, levels: int) -> str:
    if levels <= 0:
        return text

    fence: tuple[str, int] | None = None
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        fence = _update_markdown_fence(content, fence)
        lines.append(
            content if fence is not None else _demote_markdown_heading(content, levels)
        )
        lines[-1] += newline
    return "".join(lines)


def _update_markdown_fence(
    line: str, fence: tuple[str, int] | None
) -> tuple[str, int] | None:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or not stripped:
        return fence
    marker = stripped[0]
    if marker not in "`~":
        return fence
    count = len(stripped) - len(stripped.lstrip(marker))
    if count < 3:
        return fence
    if fence is None:
        return (marker, count)
    if marker == fence[0] and count >= fence[1] and not stripped[count:].strip():
        return None
    return fence


def _demote_markdown_heading(line: str, levels: int) -> str:
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    if indent > 3:
        return line
    count = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= count <= 6:
        return line
    if len(stripped) > count and not stripped[count].isspace():
        return line
    return f"{line[:indent]}{'#' * min(6, count + levels)}{stripped[count:]}"


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
        self._command = (
            str(mo.query_params().get("file", command))
            if mo.running_in_notebook()
            else command
        )
        self._state = _parse.ParseState(args=_parse.ParsedArgs.from_options(rest))
        self._cli_map = _input_map.InputMap()
        self._overrides: dict[str, typing.Any] = {}
        self._presets = presets
        self._query_params = _query_params.QueryParams.from_notebook()
        self._preset_state = self._build_preset_state()
        self._default_preset_state = self._build_default_preset_state()
        self._active_preset = self._build_active_preset()
        self._parent_group: Group | None = None
        self._markdown_heading_offset = 0
        self._subgroup_interfaces: dict[
            str, weakref.ReferenceType[interface.Interface]
        ] = {}

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> Group:
        instance = cls(["run"])
        instance._overrides = overrides
        return instance

    def subgroup(
        self,
        prefix: str,
        overrides: dict[str, typing.Any] | None = None,
        presets: Presets | None = None,
        markdown_heading_offset: int = 1,
    ) -> Group:
        """Create a child Group that prefixes all its option names with '{prefix}-'.

        Pass a nested dict under the same key to moops.run() to override controls
        in this subgroup: moops.run(notebook, casing={"style": "snake_case"}).
        Explicit overrides take precedence over those passed via moops.run().

        Pass `presets=` to give the subgroup its own preset selector; otherwise
        it inherits the parent's preset state.

        Markdown headings emitted by the subgroup are demoted by one level by
        default. Pass `markdown_heading_offset=` to customize how many levels
        this subgroup adds relative to its parent.
        """
        if markdown_heading_offset < 0:
            raise ValueError("markdown_heading_offset must be non-negative")
        child = type(self)([prefix])
        child._state = self._state
        child._cli_map = _input_map.InputMap()
        child._parent_group = self
        child._markdown_heading_offset = (
            self._markdown_heading_offset + markdown_heading_offset
        )
        child._overrides = {**self._overrides.get(prefix, {}), **(overrides or {})}
        child.option = f"{self.option}-{prefix}" if self.option else f"--{prefix}"
        child._presets = presets
        child._preset_state = (
            child._build_preset_state() if presets else self._preset_state
        )
        child._query_params = self._query_params.subgroup(prefix)
        child._default_preset_state = (
            child._build_default_preset_state()
            if presets
            else self._default_preset_state
        )
        child._active_preset = (
            child._build_active_preset() if presets else self._active_preset
        )
        return child

    def _build_preset_state(self) -> _parse.ParseState | None:
        if self._presets is None or not self._presets.selected_args:
            return None
        return self._parse_preset_args(self._presets.selected_args)

    def _build_default_preset_state(self) -> _parse.ParseState | None:
        if (
            self._presets is None
            or (
                self._query_params.params is None
                and not self._state.args.is_interactive
            )
            or self._query_params.has_user_params()
            or self._presets.get_current() is not None
            or not self._presets.default_args
        ):
            return None
        return self._parse_preset_args(self._presets.default_args)

    def _build_active_preset(self) -> str | None:
        if self._presets is None:
            return None
        if self._default_preset_state is not None:
            return "default"
        return self._presets.get_current() or None

    def _parse_preset_args(self, args_text: str) -> _parse.ParseState:
        args = _parse.ParsedArgs.from_options(shlex.split(args_text))
        return _parse.ParseState(args=args)

    def interface(self, *controls: typing.Any) -> interface.Interface:
        """
        group.interface() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.

        Pass all controls created by this group so that the registry stays in
        sync with what is actually live (handles cell reruns and deletions).
        """

        caller_path = pathlib.Path(inspect.stack()[1].filename)
        try:
            notebook_file = caller_path.resolve().relative_to(
                pathlib.Path.cwd().resolve()
            )
        except ValueError:
            notebook_file = caller_path
        extra_missing_options = tuple(
            self._missing_subgroup_interface_options(controls)
        )
        iface = interface.Interface(
            controls,
            cli_map=self._cli_map,
            overrides=self._overrides,
            notebook_name=caller_path.name,
            notebook_file=notebook_file.as_posix(),
            option_prefix=self.option,
            presets=self._presets,
            active_preset=self._active_preset,
            query_params=self._query_params,
            command=self._command,
            extra_missing_options=extra_missing_options,
        )
        if self._parent_group is not None:
            self._parent_group._register_subgroup_interface(iface)
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

    def _register_subgroup_interface(self, iface: interface.Interface) -> None:
        self._subgroup_interfaces = {
            prefix: ref
            for prefix, ref in self._subgroup_interfaces.items()
            if ref() is not None
        }
        self._subgroup_interfaces[iface.option_prefix] = weakref.ref(iface)

    def _missing_subgroup_interface_options(
        self, controls: typing.Sequence[typing.Any]
    ) -> list[str]:
        covered_ids = {
            id(ctrl) for ctrl in controls if isinstance(ctrl, interface.Interface)
        }
        missing: list[str] = []
        live_refs: dict[str, weakref.ReferenceType[interface.Interface]] = {}
        for prefix, ref in self._subgroup_interfaces.items():
            iface = ref()
            if iface is None:
                continue
            live_refs[prefix] = ref
            if id(iface) in covered_ids:
                continue
            missing.extend(iface.input_options())
        self._subgroup_interfaces = live_refs
        return missing

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        text = _demote_markdown_headings(text, self._markdown_heading_offset)
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

    def file_browser(
        self,
        initial_path: str | pathlib.Path = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        multiple: bool = True,
        on_change: typing.Callable[[str], None] | None = None,
        **kwargs: typing.Any,
    ) -> FileBrowserWithInitialSelection | mo.ui.file_browser:
        """Create a file browser UI element that maps to a CLI path option."""
        if multiple:
            raise NotImplementedError("multiple=True is not yet supported")

        opt = self._make_opt(label=label, option=option)
        initial_path = str(initial_path)
        cli = _options.FileControl(
            option=opt.option,
            metavar="PATH",
            help_text=help_text,
            default=initial_path,
        )
        value = self._get_value(cli, initial_path)
        raw_on_change = self._query_on_change(cli, on_change)

        def _on_change(infos: typing.Sequence[interface.FileBrowserFileInfo]) -> None:
            if raw_on_change is not None:
                raw_on_change(str(infos[0].path) if infos else "")

        p = pathlib.Path(value) if value else None
        browser_kwargs: dict[str, typing.Any] = dict(
            initial_path=str(p.parent) if (p and p.is_file()) else (value or ""),
            label=opt.label_with_tooltip(help_text),
            multiple=multiple,
            on_change=_on_change,
            **kwargs,
        )
        return self._cli_map.register(
            FileBrowserWithInitialSelection(default=value, **browser_kwargs)
            if value
            else mo.ui.file_browser(**browser_kwargs),
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

    def custom(
        self,
        control: typing.Any,
        fallback: typing.Any,
        *,
        value: typing.Callable[[typing.Any], typing.Any] | None = None,
    ) -> interface.CustomControl:
        """Use a custom notebook control with a moops control as the CLI fallback.

        `fallback` must be a control created by this group, such as
        `group.range_slider(...)`. In notebooks, `control` is rendered and its
        value is used. Outside notebooks, `fallback` is used so CLI parsing,
        help text, and interactive prompts keep their normal behavior.

        Pass `value=` when the notebook control's `.value` does not match the
        fallback control's value shape. It is only applied to the notebook
        control; outside notebooks, the fallback's value is used directly.
        """

        cli = self._cli_map.get(fallback)
        if cli is None:
            raise ValueError("fallback must be a control created by this Group")
        wrapped = interface.CustomControl(
            active=control if mo.running_in_notebook() else fallback,
            value=value if mo.running_in_notebook() else None,
        )
        return self._cli_map.register(wrapped, cli)

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
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        key = self._override_key(control.option)
        if key in self._overrides:
            return self._overrides[key]
        if self._preset_state is not None:
            match control.parse(self._preset_state.args):
                case _options.ParseResult(value=v):
                    self._query_params.sync(control, key, v)
                    return v
                case None:
                    self._query_params.sync(control, key, default)
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
        match control.parse(self._state.args):
            case _options.ParseError(message=msg):
                self._state.validation_errors[control.option] = msg
            case _options.ParseResult(value=v):
                return v
            case None:
                if self._state.args.is_interactive and not mo.running_in_notebook():
                    effective_default = default
                    if self._default_preset_state is not None:
                        match control.parse(self._default_preset_state.args):
                            case _options.ParseResult(value=v):
                                effective_default = v
                            case _:
                                pass
                    try:
                        self._state.args.options.update(
                            control.prompt_interactive(effective_default)
                        )
                    except KeyboardInterrupt:
                        print("\nAborted.")
                        sys.exit(1)
                    match control.parse(self._state.args):
                        case _options.ParseResult(value=v):
                            return v
                        case _:
                            pass
        if self._default_preset_state is not None:
            match control.parse(self._default_preset_state.args):
                case _options.ParseResult(value=v):
                    self._query_params.sync(control, key, v)
                    return v
                case _:
                    pass
        return default

    def _is_overridden(self, option: str) -> bool:
        return self._override_key(option) in self._overrides

    def _query_on_change(
        self,
        control: _options.InputControl,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> typing.Callable[[typing.Any], None] | None:
        return self._query_params.on_change(
            control,
            self._override_key(control.option),
            on_change,
            disabled=self._is_overridden(control.option),
        )

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
