from __future__ import annotations

import dataclasses
import enum
import inspect
import pathlib
import typing
import warnings

import marimo as mo

from . import (
    _choice_options,
    _control_mirroring,
    _input_map,
    _list_controls,
    _list_options,
    _markdown,
    _naming,
    _options,
    _parse,
    _preset_state,
    _query_params,
    _status,
    _terminal_graphics,
    _value_resolution,
    _variant,
    interface,
)
from ._custom_element import CustomElement, CustomValueFn
from ._run_button import run_button
from ._subgroup_registry import SubgroupRegistry
from ._ui_workarounds import FileBrowserWithInitialSelection
from .presets import Presets

Numeric = int | float


class OutputMode(enum.Enum):
    """Where a notebook's dual-output (e.g. ``Group.md``) should go.

    A child run via ``app.run`` cannot tell a lean CLI run from a parent that
    wants its rendered displays, so the parent sets this on the injected
    ``args``. ``output_mode = None`` silences output entirely.
    """

    NOTEBOOK = "notebook"  # emit marimo display objects
    STDOUT = "stdout"  # print text to the terminal


def _ensure_nongui_matplotlib() -> None:
    """Switch matplotlib off GUI backends for CLI figure rendering.

    Imports matplotlib if needed: when an app offloaded to a worker thread is
    the first to import it, the backend would be resolved in that thread,
    picking the GUI backend on macOS. A no-op when matplotlib is not
    installed. Notebook backends are not registered as interactive and are
    left untouched.
    """
    try:
        import matplotlib
        from matplotlib.backends.registry import BackendFilter, backend_registry
    except ImportError:
        return
    interactive = backend_registry.list_builtin(  # type: ignore[reportUnknownMemberType]
        BackendFilter.INTERACTIVE
    )
    if matplotlib.get_backend().lower() in {b.lower() for b in interactive}:
        matplotlib.use("agg")


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
        self.output_mode: OutputMode | None = (
            OutputMode.NOTEBOOK if mo.running_in_notebook() else OutputMode.STDOUT
        )
        self._input_map = _input_map.InputMap()
        self._overrides: dict[str, typing.Any] = {}
        self._presets = presets
        self._query_params = _query_params.QueryParams.from_notebook()
        self._preset_state = self._resolve_preset_state()
        self._parent_group: Group | None = None
        # Set by moops.embed() on the injected args: names of defs other than
        # "args" overridden for the embed. None means not embedded via
        # moops.embed (or overrides unknown).
        self._embedded_extra_overrides: frozenset[str] | None = None
        self._markdown_heading_offset = 0
        self._disabled = False
        self._variant_ctx = _variant.VariantContext()
        self._subgroup_registry = SubgroupRegistry()
        self._value_resolver = self._make_value_resolver()

    @property
    def is_interface_query(self) -> bool:
        """True when the notebook is being run only to obtain its interface.

        Notebooks can gate heavy computation with::

            mo.stop(args.is_interface_query)

        This is set automatically when ``--help`` is passed on the CLI, when
        the notebook is run via ``moops.interface_of()``, and when a sibling
        branch has already failed validation (so output is suppressed before
        the error is reported).
        """
        return self._is_interface_query or self._state.failed_validation

    @classmethod
    def with_overrides(cls, overrides: dict[str, typing.Any]) -> Group:
        instance = cls(["run"])
        instance._overrides = overrides
        instance._value_resolver = instance._make_value_resolver()
        # Run-as-function (moops.run) executes the notebook in a context-less
        # worker thread, so its output is CLI-like by default. Set this
        # explicitly rather than inferring it from the caller's context: the
        # Group is built here (possibly inside a notebook cell) but used during
        # app.run elsewhere. A parent collecting a child's rendered output
        # overrides this with OutputMode.NOTEBOOK on the returned Group.
        instance.output_mode = OutputMode.STDOUT
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
        child._input_map = _input_map.InputMap()
        child._parent_group = self
        child._markdown_heading_offset = (
            self._markdown_heading_offset + markdown_heading_offset
        )
        child._disabled = self._disabled
        child._variant_ctx = _variant.VariantContext()
        child._overrides = {**self._overrides.get(prefix, {}), **(overrides or {})}
        child.option = f"{self.option}-{prefix}" if self.option else f"--{prefix}"
        child._presets = presets
        child._query_params = self._query_params.subgroup(prefix)
        child._preset_state = (
            child._resolve_preset_state() if presets else self._preset_state
        )
        child._is_interface_query = self._is_interface_query
        child.output_mode = self.output_mode
        child._value_resolver = child._make_value_resolver()
        return child

    def variant(
        self,
        prefix: str,
        selector: typing.Any,
    ) -> dict[typing.Any, Group]:
        """Create branch subgroups disabled when `selector` selects another value.

        The returned dict contains subgroups named ``{prefix}-{branch}``.
        Controls from every branch should still be
        passed to ``interface()`` so marimo's DAG can see them all; this helper
        only centralizes branch namespacing and inactive-control disabling.
        """

        selector_option = _variant.control_option(selector)
        usage_placeholder = _variant.usage_placeholder(selector_option)
        selected = _variant.selected_key(selector)
        result: dict[typing.Any, Group] = {}
        for key in _variant.keys(selector):
            key_text = _variant.key_text(key)
            group = self.subgroup(f"{prefix}-{key_text}")
            is_active = selected == key
            group._disabled = self._disabled or not is_active
            heading = _variant.help_heading(selector_option, key_text)
            if is_active and not self._disabled:
                input_control = getattr(selector, "_moops_input", None)
                default_key = getattr(input_control, "default", None)
                explicit = selected != default_key or bool(
                    selector_option and self._state.args.has(selector_option)
                )
                heading += " (selected)" if explicit else " (default)"
            group._variant_ctx = _variant.VariantContext(
                help_heading=heading,
                usage_placeholder=usage_placeholder,
                usage_after_option=selector_option,
                selector_option=selector_option,
                selector_parent_prefix=self.option,
                key=key_text,
                group_prefix=prefix,
            )
            result[key] = group
        return result

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

        frame = inspect.currentframe()
        if frame is None or frame.f_back is None:
            raise RuntimeError("Could not inspect caller frame")
        try:
            caller_path = pathlib.Path(frame.f_back.f_code.co_filename)
        finally:
            del frame
        try:
            notebook_file = caller_path.resolve().relative_to(
                pathlib.Path.cwd().resolve()
            )
        except ValueError:
            notebook_file = caller_path
        extra_missing_options = tuple(self._subgroup_registry.missing_options(controls))
        iface = interface.Interface(
            controls,
            input_map=self._input_map,
            overrides=self._overrides,
            notebook_name=caller_path.name,
            notebook_file=notebook_file.as_posix(),
            option_prefix=self.option,
            presets=self._presets,
            active_preset=self._preset_state.active,
            query_params=self._query_params,
            command=self._command,
            extra_missing_options=extra_missing_options,
            disabled=self._disabled,
            variant_ctx=self._variant_ctx,
            embedded_extra_overrides=self._embedded_extra_overrides,
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

        if self.is_interface_query or self.output_mode is None:
            return None
        if notebook_only and self.output_mode is not OutputMode.NOTEBOOK:
            return None
        text = _markdown.demote_markdown_headings(text, self._markdown_heading_offset)
        if self.output_mode is OutputMode.NOTEBOOK:
            return mo.md(text)
        text = text.strip()
        stripped_fence = _markdown.strip_outer_fence(text)
        if stripped_fence is not None:
            text = stripped_fence
        elif text.startswith("`") and text.endswith("`") and text.count("`") == 2:
            text = text[1:-1]
        print(f"{text}\n")
        return None

    @property
    def graphics_supported(self) -> bool:
        """True when ``figure`` will actually render in the current context.

        Always ``True`` in notebooks (marimo renders figures); on the CLI,
        ``True`` only when stdout is a terminal speaking a supported graphics
        protocol (currently Kitty). Gate expensive plotting on this, or branch
        to a text/ASCII fallback when it is ``False``::

            mo.stop(not args.graphics_supported)

        A ``True`` on the CLI also switches matplotlib off GUI backends, so
        that the plotting it gates works when the app runs in a worker thread
        (e.g. embedded by another notebook) — GUI backends can only create
        figures on the main thread, and ``figure`` only rasterizes, never
        showing GUI windows.
        """
        if self.output_mode is OutputMode.NOTEBOOK:
            return True
        if self.output_mode is None:
            return False
        if not _terminal_graphics.detect():
            return False
        _ensure_nongui_matplotlib()
        return True

    def figure(
        self,
        fig: typing.Any,
        *,
        notebook_only: bool = False,
        dpi: int | None = None,
    ) -> mo.Html | typing.Any | None:
        """Display a figure: rendered in notebooks, inline on the terminal on CLI.

        ``fig`` may be a matplotlib ``Figure`` or ``Axes``, a PIL ``Image``, or
        raw PNG ``bytes``. In notebooks the object is returned for marimo to
        render; on the CLI it is rasterized to PNG and streamed to the terminal
        via a graphics protocol (currently Kitty). Mirrors :meth:`md`: returns
        ``None`` during interface queries, when output is silenced, or on the
        CLI. Check :attr:`graphics_supported` first if you want an ASCII
        fallback when the terminal cannot show images.
        """
        if self.is_interface_query or self.output_mode is None:
            return None
        if notebook_only and self.output_mode is not OutputMode.NOTEBOOK:
            return None
        if self.output_mode is OutputMode.NOTEBOOK:
            return mo.image(fig) if isinstance(fig, bytes) else fig
        _terminal_graphics.emit(_terminal_graphics.to_png(fig, dpi=dpi))
        return None

    def table(
        self,
        data: typing.Any,
        **kwargs: typing.Any,
    ) -> typing.Any | None:
        """Display tabular data in notebooks or plain text in CLI."""

        if self.is_interface_query or self.output_mode is None:
            return None
        if self.output_mode is OutputMode.NOTEBOOK:
            return mo.ui.table(data, **kwargs)
        format_mapping = kwargs.get("format_mapping", {})
        if format_mapping:
            if not hasattr(data, "copy"):
                raise NotImplementedError(
                    "format_mapping is only supported for data types "
                    "with a copy() method, such as pandas DataFrames"
                )
            data = data.copy()
            for column, format_value in format_mapping.items():
                if column in data:
                    fn = format_value if callable(format_value) else format_value.format
                    data[column] = data[column].map(fn)
        if hasattr(data, "to_markdown"):
            try:
                print(data.to_markdown(index=False))
            except ImportError:
                import warnings

                warnings.warn(
                    "Install tabulate for formatted table output: pip install tabulate",
                    stacklevel=2,
                )
                print(data)
        else:
            print(data)
        print()
        return None

    def progress_bar(
        self,
        collection: typing.Any = None,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        completion_title: str | None = None,
        completion_subtitle: str | None = None,
        total: int | None = None,
        show_rate: bool = True,
        show_eta: bool = True,
        remove_on_exit: bool = False,
        disabled: bool = False,
    ) -> typing.Any:
        """Show progress in notebooks or plain status lines on the CLI."""
        disabled = disabled or self.is_interface_query or self.output_mode is None
        if self.output_mode is OutputMode.NOTEBOOK:
            progress_bar = mo.status.progress_bar
        else:
            progress_bar = _status.ProgressBar
        return progress_bar(  # pyright: ignore[reportCallIssue]
            collection,
            title=title,
            subtitle=subtitle,
            completion_title=completion_title,
            completion_subtitle=completion_subtitle,
            total=total,
            show_rate=show_rate,
            show_eta=show_eta,
            remove_on_exit=remove_on_exit,
            disabled=disabled,
        )

    def spinner(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        remove_on_exit: bool = True,
    ) -> typing.Any:
        """Show a spinner in notebooks or a plain status line on the CLI."""
        if self.is_interface_query or self.output_mode is None:
            return _status.DisabledSpinner()
        return (
            mo.status.spinner
            if self.output_mode is OutputMode.NOTEBOOK
            else _status.Spinner
        )(
            title=title,
            subtitle=subtitle,
            remove_on_exit=remove_on_exit,
        )

    def _bool_control(
        self,
        widget: typing.Literal["switch", "checkbox"],
        value: bool,
        flag: str | None,
        *,
        help_text: str,
        label: str | None,
        on_change: typing.Callable[[bool], None] | None,
        **kwargs: typing.Any,
    ) -> typing.Any:
        opt = self._make_opt(label=label, option=flag, prefix="no-" if value else None)
        input_control = _options.FlagControl(
            option=opt.option,
            help_text=help_text,
            default=value,
            widget=widget,
            extra_kwargs=kwargs,
        )
        return self._register_control(opt, input_control, help_text, on_change)

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
        return self._bool_control(
            "switch",
            value,
            flag,
            help_text=help_text,
            label=label,
            on_change=on_change,
            **kwargs,
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
        return self._bool_control(
            "checkbox",
            value,
            flag,
            help_text=help_text,
            label=label,
            on_change=on_change,
            **kwargs,
        )

    def text(
        self,
        value: str = "",
        placeholder: str = "",
        kind: typing.Literal["text", "password", "email", "url"] = "text",
        max_length: int | None = None,
        *,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[str], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.text:
        """Create a text input UI element that maps to a CLI option."""

        kwargs = {
            "kind": kind,
            "max_length": max_length,
            **kwargs,
        }
        opt = self._make_opt(label=label, option=option)
        input_control = _options.TextControl(
            option=opt.option,
            metavar=placeholder or opt.metavar,
            help_text=help_text,
            default=value,
            extra_kwargs=kwargs,
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def text_area(
        self,
        value: str = "",
        placeholder: str = "",
        max_length: int | None = None,
        *,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[str], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.text_area:
        """Create a text area UI element that maps to a CLI option."""

        kwargs = {"max_length": max_length, **kwargs}
        opt = self._make_opt(label=label, option=option)
        input_control = _options.TextAreaControl(
            option=opt.option,
            metavar=placeholder or opt.metavar,
            help_text=help_text,
            default=value,
            extra_kwargs=kwargs,
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def file_browser(
        self,
        initial_path: str | pathlib.Path = "",
        filetypes: typing.Sequence[str] | None = None,
        selection_mode: typing.Literal["file", "directory", "all"]
        | typing.Sequence[typing.Literal["file", "directory"]] = "file",
        multiple: bool = True,
        restrict_navigation: bool = False,
        *,
        option: str | None = None,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        **kwargs: typing.Any,
    ) -> FileBrowserWithInitialSelection | mo.ui.file_browser:
        """Create a file browser UI element that maps to a CLI path option."""
        opt = self._make_opt(label=label, option=option)
        initial_path = str(initial_path)
        kwargs = {
            "filetypes": filetypes,
            "selection_mode": selection_mode,
            "restrict_navigation": restrict_navigation,
            **kwargs,
        }
        if multiple:
            default: str | list[str] = [initial_path] if initial_path else []
            input_control: _options.FileControl | _options.MultiFileControl = (
                _options.MultiFileControl(
                    default=default,
                    option=opt.option,
                    metavar="PATH",
                    help_text=help_text,
                    extra_kwargs=kwargs,
                )
            )
        else:
            default = initial_path
            input_control = _options.FileControl(
                default=default,
                option=opt.option,
                metavar="PATH",
                help_text=help_text,
                extra_kwargs=kwargs,
            )
        return self._register_control(opt, input_control, help_text, on_change)

    def number(
        self,
        start: float | None = None,
        stop: float | None = None,
        step: float | None = None,
        value: float | None = None,
        debounce: bool = False,
        *,
        allow_none: bool = True,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[Numeric | None], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.number:
        """Create a number input UI element that maps to a CLI option."""

        kwargs = {"step": step, "debounce": debounce, **kwargs}
        opt, input_control = self._numeric_input_control(
            start, stop, value, option, help_text, label, "number", kwargs, allow_none
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def slider(
        self,
        start: Numeric | None = None,
        stop: Numeric | None = None,
        step: Numeric | None = None,
        value: Numeric | None = None,
        debounce: bool = False,
        *,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[Numeric | None], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.slider:
        """Create a slider UI element that maps to a CLI option."""

        kwargs = {"step": step, "debounce": debounce, **kwargs}
        opt, input_control = self._numeric_input_control(
            start, stop, value, option, help_text, label, "slider", kwargs
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def range_slider(
        self,
        start: Numeric | None = None,
        stop: Numeric | None = None,
        step: Numeric | None = None,
        value: typing.Sequence[Numeric] | None = None,
        debounce: bool = False,
        orientation: typing.Literal["horizontal", "vertical"] = "horizontal",
        show_value: bool = False,
        steps: typing.Sequence[Numeric] | None = None,
        *,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[typing.Sequence[Numeric]], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.range_slider:
        """Create a range slider UI element that maps to a CLI option."""

        kwargs = {
            "debounce": debounce,
            "orientation": orientation,
            "show_value": show_value,
            **kwargs,
        }
        opt = self._make_opt(label=label, option=option)
        input_control = _options.RangeControl.from_slider(
            option=opt.option,
            metavar=opt.metavar,
            help_text=help_text,
            start=start,
            stop=stop,
            steps=steps,
            value=value,
            step=step,
            extra_kwargs=kwargs,
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def custom(
        self,
        fallback: typing.Any,
        build: typing.Callable[[typing.Any], typing.Any],
        *,
        value: CustomValueFn | None = None,
    ) -> typing.Any:
        """Pair a notebook-only component with a moops control as CLI fallback.

        `fallback` must be a control created by this group, such as
        `group.range_slider(...)`. `build(value)` constructs the notebook
        component from the fallback's resolved value; in notebooks the component
        is rendered and `value(component, fallback)` supplies its value. Outside
        notebooks, `build` is not called and the fallback is used so CLI
        parsing, help text, and interactive prompts keep their normal behavior.

        `build` is a factory (not a pre-built element) so that
        `Group.controls_from` can recreate the component when mirroring this
        control into a parent notebook. For that to work, `build` must depend
        only on data available during an interface query (avoid gating its
        inputs behind `mo.stop(args.is_interface_query)`). It receives the
        fallback's *value*, not the element: controls_from creates the fallback
        and calls build in a single cell, and marimo forbids reading a control's
        value in the cell that created it.

        Pass `value=` when the component's `.value` does not match the fallback
        control's value shape; it receives `(component, fallback)` so it can
        fall back to the fallback's live value (e.g. when nothing is selected).
        """

        inner = self._input_map.get(fallback)
        if inner is None:
            raise ValueError("fallback must be a control created by this Group")
        custom_control = dataclasses.replace(
            inner, custom_build=build, custom_value_fn=value
        )
        fallback_value = fallback._value
        element = (
            CustomElement(build(fallback_value), fallback, value)
            if mo.running_in_notebook()
            else fallback
        )
        return self._input_map.register(element, custom_control)

    @staticmethod
    def run_button(
        kind: typing.Literal["neutral", "success", "warn", "danger"] = "neutral",
        disabled: bool = False,
        tooltip: str | None = None,
        **kwargs: typing.Any,
    ):
        """Create a run button that gates notebook execution.

        In CLI context, always returns a stub with .value = True so code that
        checks `mo.stop(not btn.value)` runs unconditionally.
        """
        return run_button(kind=kind, disabled=disabled, tooltip=tooltip, **kwargs)

    def _numeric_input_control(
        self,
        start: float | None,
        stop: float | None,
        value: float | None,
        option: str | None,
        help_text: str,
        label: str | None,
        widget: typing.Literal["number", "slider"] = "number",
        extra_kwargs: dict[str, typing.Any] | None = None,
        allow_none: bool = True,
    ) -> tuple[_naming.OptionLabel, _options.NumberControl]:
        if value is None:
            value = start
        opt = self._make_opt(label=label, option=option)
        input_control = _options.NumberControl(
            option=opt.option,
            metavar=opt.metavar,
            help_text=help_text,
            default=value,
            start=start,
            stop=stop,
            widget=widget,
            allow_none=allow_none,
            extra_kwargs=extra_kwargs or {},
        )
        return opt, input_control

    def dropdown(
        self,
        options: typing.Sequence[typing.Any] | dict[str, typing.Any],
        value: typing.Any | None = None,
        allow_select_none: bool | None = None,
        searchable: bool = False,
        *,
        label: str | None = None,
        option: str | None = None,
        help_text: str,
        on_change: typing.Callable[[typing.Any], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.dropdown:
        """Create a dropdown UI element that maps to a CLI option."""

        if allow_select_none is None:
            # Preserve marimo's public signature while normalizing its default
            # for moops' CLI/query behavior.
            allow_select_none = True

        if len(options) == 0:
            raise ValueError("Dropdown options cannot be empty")
        opt = self._make_opt(label=label, option=option)
        dropdown_opts = _choice_options.option_values(options)
        value = (
            _choice_options.option_key(dropdown_opts, value)
            if value is not None
            else None
        )
        if value is None and not allow_select_none:
            value, *_ = [*dropdown_opts]
        input_control = _options.DropdownControl(
            option=opt.option,
            dropdown_opts=dropdown_opts,
            cli_opts=_choice_options.option_cli_keys(dropdown_opts),
            supports_none=allow_select_none,
            default=value,
            help_text=help_text,
            extra_kwargs={
                "allow_select_none": allow_select_none,
                "searchable": searchable,
                **kwargs,
            },
        )
        return self._register_control(opt, input_control, help_text, on_change)

    def multiselect(
        self,
        options: typing.Sequence[typing.Any] | dict[str, typing.Any],
        value: typing.Sequence[typing.Any] | None = None,
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        on_change: typing.Callable[[list[object]], None] | None = None,
        **kwargs: typing.Any,
    ) -> mo.ui.multiselect:
        """Create a multiselect UI element that maps to repeated CLI options."""
        if value is None:
            value = []
        opt = self._make_opt(label=label, option=option)
        select_opts = _choice_options.option_values(options)
        default = [_choice_options.option_value(select_opts, item) for item in value]
        input_control = _options.MultiSelectControl(
            option=opt.option,
            metavar=opt.metavar,
            help_text=help_text,
            default=default,
            select_opts=select_opts,
            extra_kwargs=kwargs,
        )
        return self._register_control(opt, input_control, help_text, on_change)

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
        return _control_mirroring.controls_from(
            self, iface, prefix=prefix, exclude=exclude
        )

    def list(
        self,
        item: typing.Callable[[Group], typing.Any],
        *,
        option: str,
        help_text: str,
        label: str | None = None,
        value: list[typing.Any] | None = None,
        on_change: typing.Callable[[list[typing.Any]], None] | None = None,
    ) -> typing.Any:
        """Create a list of repeated items with a shared anchor option.

        ``item`` is a factory called with a Group; it must create and return
        either a single moops control using the same option name as ``option``,
        or a ``controls_from(...)`` mirror whose prefix matches ``option``.
        Each scalar CLI occurrence of that option adds one item::

            --factor 2 --factor 5 --factor 10

        For mirrored subgroup items, each bare occurrence of ``option`` starts a
        new item and following unprefixed child options belong to it::

            --trip --mode car --travel-car-distance 100 --trip --mode train

        Returns a ``mo.ui.array`` whose ``.value`` is the list of item values.
        In notebooks, pass a ``mo.state`` value and setter so the add/remove
        buttons can update the list and trigger a rerun::

            get_factors, set_factors = mo.state([])
            factors = args.list(
                lambda g: g.number(value=1.0, option="--factor", help_text="Factor"),
                option="--factor",
                help_text="Factors",
                value=get_factors(),
                on_change=set_factors,
            )

        For scalar item edits, ``Group.list`` wires each item to ``on_change``.
        For mirrored ``controls_from`` items, pass ``on_change`` for add/remove
        support; the nested child controls keep their own widget values during
        normal notebook interaction.
        """
        opt = self._make_opt(label=label, option=option)

        # Probe the factory with a temporary group to discover the item's
        # InputControl. The probe has the same option prefix as self but
        # its own empty args and input_map.
        probe = type(self)(["_probe"])
        probe.option = self.option
        probe_ctrl = item(probe)
        item_template = interface.attached_interface(probe_ctrl)
        if item_template is None:
            item_input_ctrl = probe._input_map.get(probe_ctrl)
            if item_input_ctrl is None:
                raise ValueError("args.list() item factory must return a moops control")
            if not item_input_ctrl.options():
                raise ValueError("args.list() item factory must return a value control")

            list_input_ctrl = _list_options.ListControl(
                option=opt.option,
                help_text=help_text,
                default=list(value) if value is not None else [],
                item_control=item_input_ctrl,
            )
            return self._register_control(opt, list_input_ctrl, help_text, on_change)

        if item_template.option_prefix != opt.option:
            raise ValueError(
                "args.list() controls_from item prefix must match the list option"
            )
        leaves = tuple(_list_controls.subgroup_leaves(item_template))
        if not leaves:
            raise ValueError("args.list() item factory must return a value control")
        leaf_args = {
            arg
            for leaf in leaves
            for arg in (leaf.bare_control().options() | leaf.bare_control().flags())
        }
        if opt.option in leaf_args:
            raise ValueError(
                f"args.list() option {opt.option!r} conflicts with an item option"
            )
        stem = _list_controls.relative_stem(self.option, opt.option)

        def item_builder(i: int, item_dict: dict[str, typing.Any]) -> typing.Any:
            child = self.subgroup(f"{stem}-{i}")
            # Item subgroups are keyed by list index, so syncing their controls
            # to query params would key persisted values by position. A delete
            # or reorder then leaks one item's value onto whichever item lands
            # at that index. The list as a whole already round-trips through its
            # own query param, so disable per-item query params entirely.
            child._query_params = _query_params.QueryParams(params=None)
            item_prefix = f"{child.option}-{stem}"
            seed_args = _list_controls.seed_args_for_subgroup_item(
                leaves,
                list_option=opt.option,
                item_prefix=item_prefix,
                item_dict=item_dict,
            )
            child._state = _parse.ParseState(
                args=_parse.ParsedArgs.from_options(seed_args)
            )
            child._preset_state = _preset_state.PresetState(
                selected=None,
                default=None,
                active=None,
            )
            child._value_resolver = child._make_value_resolver()
            return item(child)

        list_input_ctrl = _list_options.SubgroupListControl(
            option=opt.option,
            help_text=help_text,
            default=list(value) if value is not None else [],
            item_template_default=item_template.default,
            leaves=leaves,
            item_builder=item_builder,
        )
        return self._register_control(opt, list_input_ctrl, help_text, on_change)

    def _make_value_resolver(self) -> _value_resolution.ValueResolver:
        return _value_resolution.ValueResolver(
            option_prefix=self.option,
            state=self._state,
            overrides=self._overrides,
            query_params=self._query_params,
            preset_state=self._preset_state.selected,
            default_preset_state=self._preset_state.default,
        )

    def _register_control(
        self,
        opt: _naming.OptionLabel,
        input_control: _options.InputControl,
        help_text: str,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> typing.Any:
        input_control.label = opt.label
        reset_state = self._value_resolver.query_on_change(input_control, on_change)
        control = input_control.make_element(
            self._value_resolver.get_value(input_control, input_control.default),
            label=opt.label_with_tooltip(help_text),
            disabled=self._value_resolver.is_overridden(opt.option) or self._disabled,
            on_change=reset_state,
        )
        if reset_state is not None:
            control._moops_reset_state = reset_state
        return self._input_map.register(control, input_control)

    def _make_opt(
        self, label: str | None, option: str | None, prefix: str | None = None
    ) -> _naming.OptionLabel:
        opt = _naming.OptionLabel.make(label=label, option=option, prefix=prefix)
        if self.option:
            opt = _naming.OptionLabel(
                label=opt.label,
                option=f"{self.option}-{opt.option.lstrip('-')}",
                metavar_label=opt.metavar_label,
            )
        return opt
