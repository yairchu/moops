from __future__ import annotations

import inspect
import pathlib
import typing
import warnings

import marimo as mo

from . import (
    _control_factory,
    _input_map,
    _markdown,
    _naming,
    _options,
    _parse,
    _preset_state,
    _query_params,
    _value_resolution,
    interface,
)
from ._run_button import run_button
from ._ui_workarounds import (
    FileBrowserFileInfo,
    FileBrowserWithInitialSelection,
    LockedMultiselect,
    locked_dropdown_options,
)
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
        self._command = (
            str(mo.query_params().get("file", command))
            if mo.running_in_notebook()
            else command
        )
        self._state = _parse.ParseState(args=_parse.ParsedArgs.from_options(rest))
        self._is_interface_query: bool = self._state.args.is_help
        self._cli_map = _input_map.InputMap()
        self._overrides: dict[str, typing.Any] = {}
        self._presets = presets
        self._query_params = _query_params.QueryParams.from_notebook()
        self._preset_state = self._resolve_preset_state()
        self._parent_group: Group | None = None
        self._markdown_heading_offset = 0
        self._subgroup_registry = interface.SubgroupRegistry()
        self._value_resolver = self._make_value_resolver()

    @property
    def is_interface_query(self) -> bool:
        """True when the notebook is being run only to obtain its interface.

        Notebooks can gate heavy computation with::

            mo.stop(args.is_interface_query)

        This is set automatically when ``--help`` is passed on the CLI and when
        the notebook is run via ``moops.interface_of()``.
        """
        return self._is_interface_query

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> Group:
        instance = cls(["run"])
        instance._overrides = overrides
        instance._value_resolver = instance._make_value_resolver()
        return instance

    @classmethod
    def for_interface_query(cls) -> Group:
        """Create a Group for headless interface extraction (no computation)."""
        instance = cls(["run"])
        instance._overrides = {}
        instance._is_interface_query = True
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
        _frame = inspect.currentframe()
        _caller = _frame.f_back if _frame else None
        if _caller is not None and bool(_caller.f_code.co_flags & inspect.CO_COROUTINE):
            warnings.warn(
                f"args.subgroup('{prefix}') called inside an async cell, "
                "likely the cell making the embed it is used for. "
                "Each cell re-run creates a new Group object, "
                "which causes the embedded notebook to reload and lose widget state. "
                "Move args.subgroup() to a separate sync cell instead.",
                stacklevel=2,
            )
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
        child._query_params = self._query_params.subgroup(prefix)
        child._preset_state = (
            child._resolve_preset_state() if presets else self._preset_state
        )
        child._is_interface_query = self._is_interface_query
        child._value_resolver = child._make_value_resolver()
        return child

    def _resolve_preset_state(self) -> _preset_state.PresetState:
        return _preset_state.PresetState.resolve(
            presets=self._presets,
            query_params=self._query_params,
            state=self._state,
        )

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
        extra_missing_options = tuple(self._subgroup_registry.missing_options(controls))
        iface = interface.Interface(
            controls,
            cli_map=self._cli_map,
            overrides=self._overrides,
            notebook_name=caller_path.name,
            notebook_file=notebook_file.as_posix(),
            option_prefix=self.option,
            presets=self._presets,
            active_preset=self._preset_state.active,
            query_params=self._query_params,
            command=self._command,
            extra_missing_options=extra_missing_options,
        )
        if self._parent_group is not None:
            self._parent_group._subgroup_registry.register(iface)
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

    def md(self, text: str, *, notebook_only: bool = False) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if notebook_only and not mo.running_in_notebook():
            return None
        text = _markdown.demote_markdown_headings(text, self._markdown_heading_offset)
        if mo.running_in_notebook():
            return mo.md(text)
        if self._state.args.is_help or self._is_interface_query:
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
        on_change: typing.Callable[[typing.Any], None] | None = None,
        **kwargs: typing.Any,
    ) -> FileBrowserWithInitialSelection | mo.ui.file_browser:
        """Create a file browser UI element that maps to a CLI path option."""
        opt = self._make_opt(label=label, option=option)
        initial_path = str(initial_path)
        ctrl_opts = {
            "option": opt.option,
            "metavar": "PATH",
            "help_text": help_text,
        }
        if multiple:
            default: str | list[str] = [initial_path] if initial_path else []
            cli = _options.MultiFileControl(default=default, **ctrl_opts)
        else:
            default = initial_path
            cli = _options.FileControl(default=default, **ctrl_opts)
        value = self._get_value(cli, default)
        raw_on_change = self._query_on_change(cli, on_change)

        def _on_change(infos: typing.Sequence[FileBrowserFileInfo]) -> None:
            if raw_on_change is not None:
                paths = [str(info.path) for info in infos]
                raw_on_change(paths if multiple else (paths[0] if paths else ""))

        paths = list(value) if multiple else ([value] if value else [])
        first = paths[0] if paths else ""
        p = pathlib.Path(first) if first else None
        browser_kwargs: dict[str, typing.Any] = dict(
            initial_path=str(p.parent) if (p and p.is_file()) else first,
            label=opt.label_with_tooltip(help_text),
            multiple=multiple,
            on_change=_on_change,
            **kwargs,
        )
        return self._cli_map.register(
            FileBrowserWithInitialSelection(default=paths, **browser_kwargs)
            if paths
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
                **self._control_kwargs(opt, cli, help_text, on_change),
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
        common_args: dict[str, typing.Any] = {
            "start": start,
            "stop": stop,
            "steps": steps,
        }
        cli = _options.RangeControl.from_slider(
            option=opt.option,
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            value=value,
            **common_args,
        )
        return self._cli_map.register(
            mo.ui.range_slider(
                step=step,
                value=self._get_value(cli, cli.default),
                **common_args,
                **self._control_kwargs(opt, cli, help_text, on_change),
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

    @staticmethod
    def run_button(
        **kwargs: typing.Any,
    ):
        """Create a run button that gates notebook execution.

        In CLI context, always returns a stub with .value = True so code that
        checks `mo.stop(not btn.value)` runs unconditionally.
        """
        return run_button(**kwargs)

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
        if value is None and not allow_select_none:
            value, *_ = [*options]
        cli = _options.DropdownControl(
            option=opt.option,
            dropdown_opts=options
            if isinstance(options, dict)
            else {opt: opt for opt in options},
            supports_none=allow_select_none,
            default=value,
            help_text=help_text,
        )
        if self._is_overridden(opt.option):
            options = locked_dropdown_options(self._get_value(cli, value), options)  # type: ignore[assignment]
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

    def multiselect(
        self,
        options: list[str],
        value: list[str] | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[list[str]], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.multiselect:
        """Create a multiselect UI element that maps to repeated CLI options."""
        if value is None:
            value = []
        opt = self._make_opt(label=label, option=option)
        cli = _options.MultiSelectControl(
            option=opt.option,
            metavar=opt.label.upper().replace(" ", "_"),
            help_text=help_text,
            default=list(value),
            select_opts=list(options),
        )
        selected = self._get_value(cli, value)
        if self._is_overridden(opt.option):
            return self._cli_map.register(
                LockedMultiselect(selected, opt.label_with_tooltip(help_text)),
                cli,
            )
        return self._cli_map.register(
            mo.ui.multiselect(
                options=options,
                value=selected,
                label=opt.label_with_tooltip(help_text),
                on_change=self._query_on_change(cli, on_change),
                **kwargs,
            ),
            cli,
        )

    def controls_from(
        self,
        iface: interface.Interface,
        *,
        prefix: str,
        exclude: typing.Iterable[str] = (),
    ) -> mo.ui.dictionary:
        """Create a subgroup of controls mirroring another notebook's interface.

        The returned ``mo.ui.dictionary`` is keyed by the child notebook's
        original option names and its ``.value`` can be passed to ``moops.run``.
        The controls themselves are created in a subgroup, so their CLI options
        are prefixed in the parent notebook.
        """
        child = self.subgroup(prefix)
        excluded = set(exclude)
        controls: dict[str, typing.Any] = {}
        for name, ctrl_or_sub in iface.iter_controls():
            if name in excluded:
                continue
            if isinstance(ctrl_or_sub, interface.Interface):
                controls[name] = child.controls_from(ctrl_or_sub, prefix=name)
            else:
                controls[name] = _control_factory.create_control(
                    child, iface, ctrl_or_sub
                )
        result = mo.ui.dictionary(controls)
        result._moops_interface = child.interface(*controls.values())  # type: ignore[attr-defined]
        return result

    def _make_value_resolver(self) -> _value_resolution.ValueResolver:
        return _value_resolution.ValueResolver(
            option_prefix=self.option,
            state=self._state,
            overrides=self._overrides,
            query_params=self._query_params,
            preset_state=self._preset_state.selected,
            default_preset_state=self._preset_state.default,
        )

    def _control_kwargs(
        self,
        opt: _naming.OptionLabel,
        cli: _options.InputControl,
        help_text: str,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> dict[str, typing.Any]:
        return {
            "label": opt.label_with_tooltip(help_text),
            "disabled": self._is_overridden(opt.option),
            "on_change": self._query_on_change(cli, on_change),
        }

    def _get_value(
        self,
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        return self._value_resolver.get_value(control, default)

    def _is_overridden(self, option: str) -> bool:
        return self._value_resolver.is_overridden(option)

    def _query_on_change(
        self,
        control: _options.InputControl,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> typing.Callable[[typing.Any], None] | None:
        return self._value_resolver.query_on_change(control, on_change)

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
