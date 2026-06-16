from __future__ import annotations

import dataclasses
import html
import os
import pathlib
import shlex
import sys
import typing
import urllib.parse

import marimo as mo

from . import (
    _input_map,
    _list_options,
    _marimo_controls,
    _naming,
    _options,
    _parse,
    _presets_ui,
    _query_params,
    _text_wrap,
    _variant,
)
from .presets import Presets

if typing.TYPE_CHECKING:
    from hypothesis import strategies as st


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any, ...]
    input_map: _input_map.InputMap = dataclasses.field(
        default_factory=_input_map.InputMap
    )
    overrides: dict[str, typing.Any] = dataclasses.field(default_factory=lambda: {})
    notebook_name: str = ""
    notebook_file: str = ""
    option_prefix: str = ""
    presets: Presets | None = None
    active_preset: str | None = None
    query_params: _query_params.QueryParams = dataclasses.field(
        default_factory=lambda: _query_params.QueryParams(None)
    )
    command: str = ""
    extra_missing_options: tuple[str, ...] = ()
    disabled: bool = False
    variant_ctx: _variant.VariantContext = dataclasses.field(
        default_factory=_variant.VariantContext
    )
    # Names of defs other than "args" overridden for the embed this interface
    # renders inside; None when that is unknown (not embedded via moops.embed).
    embedded_extra_overrides: frozenset[str] | None = None

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self._flatten():
            if id(ctrl) in seen_ids:
                raise ValueError("Duplicate control passed to interface")
            seen_ids.add(id(ctrl))
        self._check_duplicate_options()
        self._presets_ui = (
            _presets_ui.PresetsUI(
                self.presets,
                self,
            )
            if self.presets is not None
            else None
        )

    def _check_duplicate_options(self) -> None:
        """Reject sibling controls that resolve to the same option name.

        Only direct controls at this level are compared. Attached
        sub-interfaces (e.g. variant branches) legitimately reuse option
        names across mutually-exclusive branches and list/dict element
        controls repeat options by design, so both are skipped here — they
        are validated at their own level instead.
        """
        seen: set[str] = set()
        for ctrl in self.controls:
            if attached_interface(ctrl) is not None:
                continue
            if _marimo_controls.ui_dictionary_elements(ctrl) is not None:
                continue
            input_control = self.input_map.get(ctrl)
            if input_control is None:
                continue
            option = input_control.option
            if option in seen:
                raise ValueError(
                    f"Multiple controls map to the option {option!r}. Labels with "
                    f"parenthetical units share a base option name — e.g. "
                    f"'Length (seconds)' and 'Length (minutes)' both become "
                    f"{option!r}; give them distinct labels or pass explicit, "
                    f"different option names."
                )
            seen.add(option)

    def has_prefixed_options(self, state: _parse.ParseState) -> bool:
        """True if state has CLI options starting with this interface's prefix."""
        prefix = f"{self.option_prefix}-" if self.option_prefix else "--"
        return any(
            k
            for k in state.args.options
            if k.startswith(prefix)
            and k not in _parse.help_flags
            and k != _parse.interactive_flag
        )

    def validate(
        self,
        state: _parse.ParseState,
        *,
        active_args: _parse.ParsedArgs | None = None,
    ) -> typing.Iterator[str]:
        flags: set[str] = set()
        value_options: dict[str, _options.InputControl] = {}
        for input_control in self._input_controls(
            active_only=True,
            active_args=active_args,
        ):
            flags.update(input_control.flags())
            for option in input_control.options():
                value_options[option] = input_control
        rendered = flags | set(value_options)
        yield from (v for k, v in state.validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in state.args.unexpected:
            yield f"{unexp_text}{x}"
        for k, values in state.args.options.items():
            if k in flags:
                for v in values:
                    if v is not None:
                        yield f"{k} does not take a value, but was given: {v}"
            elif k in value_options:
                if len(values) > 1 and not value_options[k].allows_repeated_values():
                    yield f"{k} was provided multiple times"
                follower = state.args.dash_followers.get(k)
                hint = (
                    f" (use {k}={shlex.quote(follower)} "
                    "to pass a value starting with '-')"
                    if follower is not None
                    and follower not in rendered
                    and follower not in _parse.help_flags
                    and follower != _parse.interactive_flag
                    else ""
                )
                for v in values:
                    if v is None:
                        yield f"Option {k} requires a value{hint}"
            elif k not in _parse.help_flags and k != _parse.interactive_flag:
                yield f"{unexp_text}{k}"

    def apply_cli_args(self, text: str) -> tuple[str, ...]:
        """Parse a CLI command string and initialize controls from it.

        Reuses the same tokenizing and validation as a real CLI invocation.
        A leading program-name token (so the whole command shown in the
        callout round-trips unedited) is dropped before parsing. Returns
        error messages if the string is malformed (e.g. unbalanced quotes),
        names unknown options, or gives a value the wrong type; in that case
        controls are left unchanged. On success the controls (and their query
        params) are reset to the parsed values and ``()`` is returned.

        Subgroups that own their presets are not initialized from ``text``:
        the parsed args are not threaded into them. As with any preset change
        they are reset through their own preset mechanism (see
        ``_reset_notebook_state``), independently of the edited command.
        """
        # Fold shell line-continuations first: the box shows the command
        # wrapped with `\`-continuations, but shlex would otherwise leave the
        # escaped newline behind as a stray token.
        text = text.replace("\\\n", " ")
        try:
            tokens = shlex.split(text)
        except ValueError as exc:
            return (f"Could not parse arguments: {exc}",)
        if tokens[:2] == ["uv", "run"]:
            tokens = tokens[2:]
        commands = {self.command, pathlib.PurePath(self.command).name}
        if tokens and tokens[0] in commands:
            tokens = tokens[1:]
        args = _parse.ParsedArgs.from_options(tokens)
        state = _parse.ParseState(args=args)
        for input_control in self._input_controls(
            active_only=True,
            active_args=args,
        ):
            match input_control.parse(args):
                case _options.ParseError(message=msg):
                    state.validation_errors[input_control.option] = msg
                case _:
                    pass
        errors = tuple(self.validate(state, active_args=args))
        if errors:
            return errors
        self._reset_notebook_state(None, args)
        return ()

    def help(self) -> str:
        usage_parts = list(self._format_usage_parts(_usage_placeholders(self)))
        if any(self._input_controls(active_only=True)):
            usage_parts.append("[--interactive]")
        usage_parts.append("[-h/--help]")
        name = pathlib.PurePath(self.command).name
        prefix = f"Usage: {name} "
        segments = [_text_wrap.wrap_usage(prefix, usage_parts)]
        help_lines = list(self._format_help_lines())
        if help_lines:
            segments.append("\n".join(help_lines))
        return "\n\n".join(segments)

    def _format_help_lines(self) -> typing.Iterator[str]:
        prev_was_group_with_content = False
        for ctrl in self.controls:
            if (sub_iface := attached_interface(ctrl)) is not None:
                lines = list(sub_iface._format_help_lines())
                if lines and sub_iface.variant_ctx.help_heading:
                    yield ""
                    yield f"{sub_iface.variant_ctx.help_heading}:"
                yield from lines
                prev_was_group_with_content = bool(lines)
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    if prev_was_group_with_content:
                        yield ""
                    for help_line in input_control.format_help_lines():
                        yield from _text_wrap.wrap_help_line(help_line)
                prev_was_group_with_content = False

    def _format_usage_parts(
        self, placeholders_by_option: dict[str, str]
    ) -> typing.Iterator[str]:
        for ctrl in self.controls:
            sub_iface = attached_interface(ctrl)
            if sub_iface is None:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield from input_control.format_usage_parts()
                    for option in input_control.options() | input_control.flags():
                        if placeholder := placeholders_by_option.pop(option, None):
                            yield placeholder

            elif not sub_iface.variant_ctx.usage_placeholder:
                yield from sub_iface._format_usage_parts(placeholders_by_option)

    @property
    def default(self) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {
            name: ctrl_or_sub.default  # type: ignore
            for name, ctrl_or_sub in self.iter_controls()
            if isinstance(ctrl_or_sub, Interface) or hasattr(ctrl_or_sub, "default")
        }
        return result

    def strategy(self) -> st.SearchStrategy[dict[str, typing.Any]]:
        from hypothesis import strategies as st

        strategies: dict[str, st.SearchStrategy[typing.Any]] = {
            name: ctrl_or_sub.strategy() for name, ctrl_or_sub in self.iter_controls()
        }
        return st.fixed_dictionaries(strategies).map(
            lambda d: {k: v for k, v in d.items() if v is not None}
        )

    def _input_controls(
        self,
        *,
        active_only: bool,
        root: Interface | None = None,
        active_args: _parse.ParsedArgs | None = None,
        include_overridden: bool = False,
    ) -> typing.Iterator[_options.InputControl]:
        root = self if root is None else root
        if active_only and self._is_inactive(root, active_args=active_args):
            return
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                yield from iface._input_controls(
                    active_only=active_only,
                    root=root,
                    active_args=active_args,
                    include_overridden=include_overridden,
                )
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and (
                    include_overridden or not self._is_overridden(input_control)
                ):
                    yield input_control

    def _is_inactive(
        self,
        root: Interface,
        *,
        active_args: _parse.ParsedArgs | None = None,
    ) -> bool:
        ctx = self.variant_ctx
        if ctx.group_prefix is not None and ctx.selector_option is not None:
            selected = selected_value_for_option(root, ctx.selector_option, active_args)
            if selected is not None:
                return ctx.key != _variant.key_text(selected)
        return self.disabled

    def input_options(self) -> list[str]:
        return [
            input_control.option
            for input_control in self._input_controls(active_only=False)
        ]

    def _key(self, input_control: _options.InputControl) -> str:
        return _naming.option_to_key(input_control.option, self.option_prefix)

    def iter_controls(
        self,
    ) -> typing.Iterator[tuple[str, Interface | _options.InputControl]]:
        """Yield one entry per top-level control, preserving subgroup structure.

        Yields ``(name, sub_iface)`` for subgroup controls and
        ``(key, input_control)`` for leaf controls (skipping overridden ones).
        Used by ``Group.controls_from`` to mirror another notebook's structure.
        """
        for ctrl in self.controls:
            if (sub_iface := attached_interface(ctrl)) is not None:
                sub_prefix = sub_iface.option_prefix[len(self.option_prefix) :].lstrip(
                    "-"
                )
                yield sub_prefix, sub_iface
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield self._key(input_control), input_control

    def _is_overridden(self, input_control: _options.InputControl) -> bool:
        return self._key(input_control) in self.overrides

    def cur_values(self, *, include_overridden: bool = False) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                result.update(iface.cur_values(include_overridden=include_overridden))
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and (
                    include_overridden or not self._is_overridden(input_control)
                ):
                    result[input_control.option] = _marimo_controls.ctrl_value(ctrl)
        return result

    def preset_args(self) -> str:
        return self._current_args()

    def _current_args(self) -> str:
        return " ".join(self._arg_groups())

    def _arg_groups(self) -> list[str]:
        """Current CLI args grouped into wrap-friendly chunks.

        Each entry is the space-joined tokens for one chunk: a single option
        (e.g. ``"--trip-0-mode car"``), or one item of a list control (e.g.
        ``"--trip --travel-car-distance 125"``) so long repeated-option commands
        wrap per item. Used both for the flat ``_current_args`` string and for
        the line-wrapped command shown in the script callout.
        """
        return [" ".join(tokens) for tokens in self._token_groups()]

    def _token_groups(self, *, include_overridden: bool = False) -> list[list[str]]:
        values = self.cur_values(include_overridden=include_overridden)
        return [
            tokens
            for input_control in self._input_controls(
                active_only=True, include_overridden=include_overridden
            )
            if input_control.option in values
            for tokens in input_control.format_value_groups(
                values[input_control.option]
            )
        ]

    def _standalone_arg_groups(self) -> list[str]:
        """Current CLI args spelled for running the notebook standalone.

        Rewrites option tokens to drop this interface's embed prefix. Working
        at the token level covers every control type uniformly, including
        list anchors and ``--no-`` aux flags that embed the prefixed name.
        Overridden controls are included: their values are fixed by the
        embedding parent, so standalone the CLI must pass them explicitly.
        """
        return [
            " ".join(self._strip_embed_prefix(token) for token in tokens)
            for tokens in self._token_groups(include_overridden=True)
        ]

    def _strip_embed_prefix(self, token: str) -> str:
        stem = self.option_prefix.lstrip("-")
        for head in ("--", "--no-"):
            if token.startswith(f"{head}{stem}-"):
                return f"{head}{token[len(head) + len(stem) + 1 :]}"
        return token

    def missing_options(self) -> list[str]:
        covered = {
            input_control.option
            for ctrl in self.controls
            if attached_interface(ctrl) is None
            for input_control in [self.input_map.get(ctrl)]
            if input_control is not None
        }
        return [
            input_control.option
            for input_control in self.input_map.registered_options()
            if input_control.option not in covered
        ] + list(self.extra_missing_options)

    def validate_or_exit(self, state: _parse.ParseState) -> None:
        issues = list(self.validate(state))
        if issues:
            print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
            print()
        if state.args.is_help or issues:
            print(self.help())
            sys.exit(1 if issues else 0)

    def _mime_(self) -> tuple[str, str]:
        if self.option_prefix:
            return self._subgroup_summary()._mime_()  # type: ignore
        return self._root_panel()._mime_()  # type: ignore

    def _subgroup_summary(self) -> mo.Html:
        if not self.notebook_name:
            return mo.md("Input bundle with no notebook name")
        notebook_name = html.escape(self.notebook_name)
        href = html.escape(self._standalone_url(), quote=True)
        link = mo.md(
            f'<a href="{href}" target="_blank" rel="noopener">'
            f"An embedded instance of `{notebook_name}`</a>"
        )
        if self.embedded_extra_overrides != frozenset():
            # None: embedded outside moops.embed, so overrides are unknown.
            # Non-empty: the parent injected defs beyond args, so no CLI
            # command can reproduce this setup.
            return link
        command = _wrap_command(self.notebook_file, self._standalone_arg_groups())
        return mo.vstack(
            [link, mo.md(f"To run as a standalone script:\n```\n{command}\n```")]
        )

    def _standalone_url(self) -> str:
        values = self._standalone_query_values()
        query = urllib.parse.urlencode({"file": self.notebook_file, **values})
        return f"/?{query}"

    def _standalone_query_values(self, prefix: str = "") -> dict[str, str]:
        """Query params reproducing this notebook's state when run standalone.

        ``prefix`` is the dotted query-param path of this interface relative to
        the standalone root (empty at the root). A real subgroup keeps its
        segment so its controls round-trip under the same dotted key the
        subgroup reads back (e.g. ``sub.mode``); the embedded-summary link calls
        this on the subgroup itself, so there ``prefix`` is empty and its
        controls go flat, matching the embedded notebook running as root.
        """
        values: dict[str, str] = {}
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                segment = ctrl._query_segment_below(self.query_params.prefix)
                child = (
                    f"{prefix}.{segment}" if prefix and segment else segment or prefix
                )
                values.update(ctrl._standalone_query_values(child))
            elif (sub_iface := attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(sub_iface, prefix))
            else:
                self._add_query_value(values, ctrl, self.input_map, prefix)
        return values

    def _query_segment_below(self, parent_prefix: str) -> str:
        """This interface's dotted query path relative to ``parent_prefix``."""
        prefix = self.query_params.prefix
        if parent_prefix and prefix.startswith(f"{parent_prefix}."):
            return prefix[len(parent_prefix) + 1 :]
        if parent_prefix and prefix == parent_prefix:
            return ""
        return prefix

    def _controls_from_query_values(
        self, sub_iface: Interface, prefix: str = ""
    ) -> dict[str, str]:
        """Collect standalone query values for a controls_from mirror.

        Uses this interface's key scheme (our option_prefix) so the resulting
        URL params match the parent notebook's parameter namespace.
        """
        values: dict[str, str] = {}
        for ctrl in sub_iface.controls:
            if (nested := attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(nested, prefix))
            else:
                self._add_query_value(values, ctrl, sub_iface.input_map, prefix)
        return values

    def _add_query_value(
        self,
        values: dict[str, str],
        ctrl: typing.Any,
        input_map: _input_map.InputMap,
        prefix: str = "",
    ) -> None:
        input_control = input_map.get(ctrl)
        if input_control is None:
            return
        value = input_control.format_query_value(_marimo_controls.ctrl_value(ctrl))
        if value is not None:
            leaf = self._key(input_control)
            full = f"{prefix}.{leaf}" if prefix else leaf
            values[_query_params.escape_url_key(full)] = value

    def _root_panel(self) -> mo.Html:
        args = self._current_args()
        body_items: list[typing.Any] = [mo.md("This notebook also works as a script:")]
        command = _wrap_command(self.command, self._arg_groups())
        missing_options = self.missing_options()
        kind = "warn" if missing_options else "info"
        if self._presets_ui is not None:
            # With presets the command line itself is editable: edit (or paste)
            # a command and commit to initialize every control from it. The box
            # shows the whole command, program name included and wrapped the same
            # way as the read-only callout, so it round-trips (apply_cli_args
            # folds the `\`-continuations back together before parsing).
            body_items.append(self._presets_ui.command_box(command))
            # A failed edit turns the whole callout into an alert and shows the
            # errors inline, in the same fixed-width form the CLI prints them.
            errors = self._presets_ui.pending_errors()
            if errors:
                kind = "danger"
                error_lines = "\n".join(f"- {error}" for error in errors)
                body_items.append(mo.md(f"```\nArgument errors:\n{error_lines}\n```"))
        else:
            body_items.append(mo.md(f"```\n{command}\n```"))
        missing_options_msg = (
            f"\nMissing options: {', '.join(f'`{opt}`' for opt in missing_options)}"
            if missing_options
            else ""
        )
        if any(self._input_controls(active_only=True)):
            help_text = self.help()
            usage = (
                f"```\n{help_text}\n```\n"
                if len(help_text.splitlines()) <= 3
                else (
                    f"<details><summary>Usage</summary>\n\n"
                    f"```\n{help_text}\n```\n</details>\n"
                )
            )
            body_items.append(mo.md(f"{usage}{missing_options_msg}"))
        elif missing_options_msg:
            body_items.append(mo.md(missing_options_msg))
        items: list[typing.Any] = [mo.callout(mo.vstack(body_items), kind)]
        if self._presets_ui is not None:
            items.append(self._presets_ui.layout(args))
        return mo.vstack(items)

    def select_preset(self, preset: str | None) -> None:
        self._select_preset(preset)

    def _select_preset(self, preset: str | None) -> None:
        assert self.presets is not None
        self.presets.select("" if preset is None else preset)
        self._reset_notebook_state(preset)
        if preset is None:
            self._clear_query_params()

    def _reset_notebook_state(
        self,
        preset: str | None,
        args: _parse.ParsedArgs | None = None,
    ) -> None:
        if args is None:
            assert self.presets is not None
            args = _parse.ParsedArgs.from_options(
                shlex.split(self.presets.args_for(preset))
            )
        for ctrl in self.controls:
            iface = attached_interface(ctrl)
            if iface is not None:
                iface._reset_notebook_state(
                    preset,
                    None if iface.presets is not None else args,
                )
                continue
            elements = _marimo_controls.ui_dictionary_elements(ctrl)
            if elements is None:
                self._reset_control_notebook_state(ctrl, args)
                continue
            for child in elements.values():
                Interface((child,), self.input_map)._reset_notebook_state(
                    preset,
                    args,
                )

    def _reset_control_notebook_state(
        self,
        ctrl: typing.Any,
        args: _parse.ParsedArgs,
    ) -> None:
        input_control = self.input_map.get(ctrl)
        reset_state = getattr(ctrl, "_moops_reset_state", None)
        if (
            input_control is None
            or not callable(reset_state)
            or self._is_overridden(input_control)
        ):
            return
        reset_state(_reset_value(input_control, args))

    def _clear_query_params(self) -> None:
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                iface._clear_query_params()
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None:
                    self.query_params.clear(self._key(input_control))

    def _flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                yield from iface._flatten()
            elif (
                elements := _marimo_controls.ui_dictionary_elements(ctrl)
            ) is not None:
                for child in elements.values():
                    yield from Interface((child,), self.input_map)._flatten()
            else:
                yield ctrl


def attached_interface(ctrl: typing.Any) -> Interface | None:
    if isinstance(ctrl, Interface):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    assert iface is None or isinstance(iface, Interface)
    return iface


def _wrap_command(command: str, groups: list[str]) -> str:
    if _should_use_uv_run(command):
        return _text_wrap.wrap_command("uv", [f"run {shlex.quote(command)}", *groups])
    return _text_wrap.wrap_command(command, groups)


def _should_use_uv_run(command: str) -> bool:
    path = pathlib.Path(command)
    return (
        "UV_RUN_RECURSION_DEPTH" in os.environ
        and path.is_file()
        and not os.access(path, os.X_OK)
    )


def _reset_value(
    input_control: _options.InputControl,
    args: _parse.ParsedArgs,
) -> typing.Any:
    match input_control.parse(args):
        case _options.ParseResult(value=value):
            return value
        case _:
            return _empty_reset_value(input_control)


def _empty_reset_value(input_control: _options.InputControl) -> typing.Any:
    if isinstance(
        input_control,
        (_list_options.ListControl, _list_options.SubgroupListControl),
    ):
        return []
    return input_control.default


def selected_value_for_option(
    iface: Interface,
    selector_option: str | None,
    args: _parse.ParsedArgs | None = None,
) -> typing.Any:
    """Find the variant selector's current value within ``iface``.

    Walks nested interfaces for the control whose option is
    ``selector_option``. With ``args is None`` the value is read from the live
    widget; otherwise it is parsed from ``args`` (falling back to an empty
    reset value when the option is absent).
    """
    if selector_option is None:
        return None
    for ctrl in iface.controls:
        sub_iface = attached_interface(ctrl)
        if sub_iface is not None:
            selected = selected_value_for_option(sub_iface, selector_option, args)
            if selected is not None:
                return selected
            continue
        input_control = iface.input_map.get(ctrl)
        if input_control is None or input_control.option != selector_option:
            continue
        if args is None:
            return _variant.selected_key(ctrl)
        match input_control.parse(args):
            case _options.ParseResult(value=value):
                return value
            case _:
                return _empty_reset_value(input_control)
    return None


def _usage_placeholders(iface: Interface) -> dict[str, str]:
    result: dict[str, str] = {}
    _collect_usage_placeholders(iface, result)
    return result


def _collect_usage_placeholders(
    iface: Interface,
    result: dict[str, str],
) -> None:
    ctx = iface.variant_ctx
    if ctx.usage_placeholder and ctx.usage_after_option:
        result.setdefault(ctx.usage_after_option, ctx.usage_placeholder)
    for ctrl in iface.controls:
        if sub_iface := attached_interface(ctrl):
            _collect_usage_placeholders(sub_iface, result)
