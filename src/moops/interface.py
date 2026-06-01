import dataclasses
import html
import sys
import typing
import urllib.parse

import marimo as mo
from hypothesis import strategies as st

from . import (
    _input_map,
    _marimo_controls,
    _options,
    _parse,
    _presets_ui,
    _query_params,
    _text_wrap,
    _variant,
)
from .presets import Presets


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any]
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
    help_heading: str | None = None
    usage_placeholder: str | None = None
    usage_after_option: str | None = None
    disabled: bool = False
    variant_selector_option: str | None = None
    variant_selector_parent_prefix: str = ""
    variant_key: str | None = None
    variant_group_prefix: str | None = None

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self._flatten():
            if id(ctrl) in seen_ids:
                raise ValueError("Duplicate control passed to interface")
            seen_ids.add(id(ctrl))
        self._presets_ui = (
            _presets_ui.PresetsUI(
                self.presets,
                self.active_preset,
                self._select_preset,
                self._current_args,
            )
            if self.presets is not None
            else None
        )

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

    def validate(self, state: _parse.ParseState) -> typing.Iterator[str]:
        flags: set[str] = set()
        value_options: dict[str, _options.InputControl] = {}
        for input_control in self._input_controls(active_only=True):
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
                for v in values:
                    if v is None:
                        yield f"Option {k} requires a value"
            elif k not in _parse.help_flags and k != _parse.interactive_flag:
                yield f"{unexp_text}{k}"

    def help(self) -> str:
        usage_parts = list(self._format_usage_parts(_usage_placeholders(self)))
        if any(self._input_controls(active_only=True)):
            usage_parts.append("[--interactive]")
        usage_parts.append("[-h/--help]")
        name = self.command.rsplit("/", 1)[-1]
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
                if lines and sub_iface.help_heading:
                    yield ""
                    yield f"{sub_iface.help_heading}:"
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

            elif not sub_iface.usage_placeholder:
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
        strategies: dict[str, st.SearchStrategy[typing.Any]] = {
            name: ctrl_or_sub.strategy() for name, ctrl_or_sub in self.iter_controls()
        }
        return st.fixed_dictionaries(strategies).map(
            lambda d: {k: v for k, v in d.items() if v is not None}
        )

    def _input_controls(
        self, *, active_only: bool, root: "Interface | None" = None
    ) -> typing.Iterator[_options.InputControl]:
        root = self if root is None else root
        if active_only and self._is_inactive(root):
            return
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                yield from iface._input_controls(active_only=active_only, root=root)
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield input_control

    def _is_inactive(self, root: "Interface") -> bool:
        if (
            self.variant_group_prefix is not None
            and self.variant_selector_option is not None
        ):
            selected = selected_value_for_option(root, self.variant_selector_option)
            if selected is not None:
                return self.variant_key != _variant.key_text(selected)
        return self.disabled

    def input_options(self) -> list[str]:
        return [
            input_control.option
            for input_control in self._input_controls(active_only=False)
        ]

    def _key(self, input_control: _options.InputControl) -> str:
        option = input_control.option[len(self.option_prefix) :].lstrip("-")
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def iter_controls(
        self,
    ) -> typing.Iterator[tuple[str, "Interface | _options.InputControl"]]:
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

    def cur_values(self) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for ctrl in self.controls:
            if (iface := attached_interface(ctrl)) is not None:
                result.update(iface.cur_values())
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    result[input_control.option] = _marimo_controls.ctrl_value(ctrl)
        return result

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
        values = self.cur_values()
        return [
            " ".join(tokens)
            for input_control in self._input_controls(active_only=True)
            if input_control.option in values
            for tokens in input_control.format_value_groups(
                values[input_control.option]
            )
        ]

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
        return mo.md(
            f'<a href="{href}" target="_blank" rel="noopener">'
            f"An embedded instance of `{notebook_name}`</a>"
        )

    def _standalone_url(self) -> str:
        values = self._standalone_query_values()
        query = urllib.parse.urlencode({"file": self.notebook_file, **values})
        return f"/?{query}"

    def _standalone_query_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                values.update(ctrl._standalone_query_values())
            elif (sub_iface := attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(sub_iface))
            else:
                self._add_query_value(values, ctrl, self.input_map)
        return values

    def _controls_from_query_values(self, sub_iface: "Interface") -> dict[str, str]:
        """Collect standalone query values for a controls_from mirror.

        Uses this interface's key scheme (our option_prefix) so the resulting
        URL params match the parent notebook's parameter namespace.
        """
        values: dict[str, str] = {}
        for ctrl in sub_iface.controls:
            if (nested := attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(nested))
            else:
                self._add_query_value(values, ctrl, sub_iface.input_map)
        return values

    def _add_query_value(
        self,
        values: dict[str, str],
        ctrl: typing.Any,
        input_map: _input_map.InputMap,
    ) -> None:
        input_control = input_map.get(ctrl)
        if input_control is None:
            return
        value = input_control.format_query_value(_marimo_controls.ctrl_value(ctrl))
        if value is not None:
            values[_query_params.escape_url_key(self._key(input_control))] = value

    def _root_panel(self) -> mo.Html:
        args = self._current_args()
        name = self.command.rsplit("/", 1)[-1]
        current_command = _text_wrap.wrap_command(name, self._arg_groups())
        missing_options = self.missing_options()
        missing_options_msg = (
            f"\nMissing options: {', '.join(f'`{opt}`' for opt in missing_options)}"
            if missing_options
            else ""
        )
        items: list[typing.Any] = [
            mo.callout(
                mo.md(
                    "This notebook also works as a script:\n\n"
                    f"```\n{current_command}\n```\n\n"
                    f"<details><summary>Usage</summary>\n\n```\n{self.help()}\n```\n</details>\n\n"
                    f"{missing_options_msg}"
                ),
                "warn" if missing_options else "info",
            )
        ]
        if self._presets_ui is not None:
            items.append(self._presets_ui.layout(args))
        return mo.vstack(items)

    def _select_preset(self, preset: str | None) -> None:
        assert self.presets is not None
        self.presets.select("" if preset is None else preset)
        if preset is None:
            self._clear_query_params()

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
    return iface if isinstance(iface, Interface) else None


def selected_value_for_option(
    iface: Interface, selector_option: str | None
) -> typing.Any:
    if selector_option is None:
        return None
    for ctrl in iface.controls:
        sub_iface = attached_interface(ctrl)
        if sub_iface is not None:
            selected = selected_value_for_option(sub_iface, selector_option)
            if selected is not None:
                return selected
            continue
        input_control = iface.input_map.get(ctrl)
        if input_control is not None and input_control.option == selector_option:
            return _variant.selected_key(ctrl)
    return None


def _usage_placeholders(iface: Interface) -> dict[str, str]:
    result: dict[str, str] = {}
    _collect_usage_placeholders(iface, result)
    return result


def _collect_usage_placeholders(
    iface: Interface,
    result: dict[str, str],
) -> None:
    if iface.usage_placeholder and iface.usage_after_option:
        result.setdefault(iface.usage_after_option, iface.usage_placeholder)
    for ctrl in iface.controls:
        if sub_iface := attached_interface(ctrl):
            _collect_usage_placeholders(sub_iface, result)
