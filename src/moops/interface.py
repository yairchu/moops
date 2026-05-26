import dataclasses
import html
import sys
import typing
import urllib.parse
import weakref

import marimo as mo
from hypothesis import strategies as st
from marimo._plugins.ui._core.ui_element import UIElement

from . import _input_map, _options, _parse, _query_params
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

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self._flatten():
            if id(ctrl) in seen_ids:
                raise ValueError("Duplicate control passed to interface")
            seen_ids.add(id(ctrl))
        self._presets_ui = (
            _PresetsUI(
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
        for input_control in self._active_input_controls():
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
        usage_parts.extend(("[--interactive]", "[-h/--help]"))
        name = self.command.rsplit("/", 1)[-1]
        segments = [f"Usage: {name} {' '.join(usage_parts)}"]
        help_lines = list(self._format_help_lines())
        if help_lines:
            segments.append("\n".join(help_lines))
        return "\n\n".join(segments)

    def _format_help_lines(self) -> typing.Iterator[str]:
        for ctrl in self.controls:
            if (sub_iface := _attached_interface(ctrl)) is not None:
                lines = list(sub_iface._format_help_lines())
                if lines and sub_iface.help_heading:
                    yield ""
                    yield f"{sub_iface.help_heading}:"
                yield from lines
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield from input_control.format_help_lines()

    def _format_usage_parts(
        self, placeholders_by_option: dict[str, str]
    ) -> typing.Iterator[str]:
        for ctrl in self.controls:
            sub_iface = _attached_interface(ctrl)
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
            if isinstance(ctrl_or_sub, Interface)
            or hasattr(ctrl_or_sub, "default")
        }
        return result

    def strategy(self) -> st.SearchStrategy[dict[str, typing.Any]]:
        strategies: dict[str, st.SearchStrategy[typing.Any]] = {
            name: ctrl_or_sub.strategy() for name, ctrl_or_sub in self.iter_controls()
        }
        return st.fixed_dictionaries(strategies).map(
            lambda d: {k: v for k, v in d.items() if v is not None}
        )

    def _all_input_controls(self) -> typing.Iterator[_options.InputControl]:
        for ctrl in self.controls:
            if (iface := _attached_interface(ctrl)) is not None:
                yield from iface._all_input_controls()
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield input_control

    def _active_input_controls(self) -> typing.Iterator[_options.InputControl]:
        if self.disabled:
            return
        for ctrl in self.controls:
            if (iface := _attached_interface(ctrl)) is not None:
                yield from iface._active_input_controls()
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    yield input_control

    def input_options(self) -> list[str]:
        return [input_control.option for input_control in self._all_input_controls()]

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
            if (sub_iface := _attached_interface(ctrl)) is not None:
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
            if (iface := _attached_interface(ctrl)) is not None:
                result.update(iface.cur_values())
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None and not self._is_overridden(input_control):
                    result[input_control.option] = _ctrl_value(ctrl)
        return result

    def _current_args(self) -> str:
        values = self.cur_values()
        return " ".join(
            arg
            for input_control in self._active_input_controls()
            if input_control.option in values
            for arg in input_control.format_value(values[input_control.option])
        )

    def missing_options(self) -> list[str]:
        covered = {
            input_control.option
            for ctrl in self.controls
            if _attached_interface(ctrl) is None
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
            elif (sub_iface := _attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(sub_iface))
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is None:
                    continue
                value = input_control.format_query_value(_ctrl_value(ctrl))
                if value is not None:
                    key = _query_params.escape_url_key(self._key(input_control))
                    values[key] = value
        return values

    def _controls_from_query_values(self, sub_iface: "Interface") -> dict[str, str]:
        """Collect standalone query values for a controls_from mirror.

        Uses this interface's key scheme (our option_prefix) so the resulting
        URL params match the parent notebook's parameter namespace.
        """
        values: dict[str, str] = {}
        for ctrl in sub_iface.controls:
            if (nested := _attached_interface(ctrl)) is not None:
                values.update(self._controls_from_query_values(nested))
            else:
                input_control = sub_iface.input_map.get(ctrl)
                if input_control is None:
                    continue
                value = input_control.format_query_value(_ctrl_value(ctrl))
                if value is not None:
                    key = _query_params.escape_url_key(self._key(input_control))
                    values[key] = value
        return values

    def _root_panel(self) -> mo.Html:
        args = self._current_args()
        name = self.command.rsplit("/", 1)[-1]
        current_command = f"{name} {args}" if args else name
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
            if (iface := _attached_interface(ctrl)) is not None:
                iface._clear_query_params()
            else:
                input_control = self.input_map.get(ctrl)
                if input_control is not None:
                    self.query_params.clear(self._key(input_control))

    def _flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if (iface := _attached_interface(ctrl)) is not None:
                yield from iface._flatten()
            elif (elements := _ui_dictionary_elements(ctrl)) is not None:
                for child in elements.values():
                    yield from Interface((child,), self.input_map)._flatten()
            else:
                yield ctrl


class _PresetsUI:
    def __init__(
        self,
        presets: Presets,
        active_preset: str | None,
        select_preset: typing.Callable[[str | None], None],
        get_args: typing.Callable[[], str],
    ) -> None:
        self._presets = presets
        self._active_preset = active_preset
        self._select_preset = select_preset
        self._name_input = mo.ui.text(label="as", placeholder="default")
        self._save_btn = mo.ui.button(
            label="Save",
            on_click=lambda _: presets.save(
                self._name_input.value or "default", get_args()
            ),
        )
        rename_placeholder = (
            "preset name" if self._active_preset == "default" else "default"
        )
        self._rename_input = mo.ui.text(label="to", placeholder=rename_placeholder)
        self._rename_btn = mo.ui.button(
            label="Rename",
            on_click=lambda _: presets.rename(
                self._active_preset or "",
                self._rename_input.value or "default",
            ),
        )
        self._reset_btn = mo.ui.button(
            label="Clear changes",
            on_click=lambda _: self._select_preset(self._active_preset),
        )
        self._reset_default_btn = mo.ui.button(
            label="Reset default",
            on_click=lambda _: presets.delete("default"),
        )

    def layout(self, args: str) -> mo.Html:
        # Stored on self so the dropdown isn't garbage-collected after layout()
        # returns — mo.hstack only retains rendered HTML, not the elements, and
        # marimo's UIElementRegistry holds weakrefs. If the element is GC'd,
        # frontend interactions can't find it and on_change never fires.
        self._dropdown = mo.ui.dropdown(
            label="Preset",
            options=list(self._presets.list()),
            allow_select_none=True,
            value=self._active_preset,
            on_change=self._select_preset,
        )
        active_args = self._presets.args_for(self._active_preset)
        controls: list[typing.Any] = [self._dropdown]
        if args != active_args:
            controls.extend([self._reset_btn, self._save_btn, self._name_input])
        elif self._active_preset:
            controls.extend([self._rename_btn, self._rename_input])
        if self._active_preset is None and self._presets.default_args:
            controls.append(self._reset_default_btn)
        return mo.hstack(
            controls,
            justify="start",
        )


class CustomControl(UIElement[typing.Any, typing.Any]):
    """Wrap a notebook-only control with a CLI-compatible fallback control."""

    def __init__(
        self,
        *,
        active: typing.Any,
        value: typing.Callable[[typing.Any], typing.Any] | None = None,
    ) -> None:
        if not isinstance(active, UIElement):
            raise TypeError("custom controls must wrap a marimo UIElement")
        self._active: UIElement[typing.Any, typing.Any] = active
        self._value = value or _default_custom_value
        # Deliberately skip super().__init__(): we reuse the wrapped element's
        # identity so marimo's reactive DAG treats this as the same element.
        # Calling super().__init__() would register a new element and ID.
        self._id = active._id
        self._lens = active._lens

    @property
    def value(self) -> typing.Any:
        return self._value(self._active)

    @value.setter
    def value(self, value: typing.Any) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")

    def _mime_(self) -> tuple[str, str]:  # type: ignore[override]
        return self._active._mime_()

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._active, name)


def _ctrl_value(ctrl: typing.Any) -> typing.Any:
    if isinstance(ctrl, mo.ui.file_browser):
        multiple = getattr(ctrl, "_component_args", {}).get("multiple", True)
        if multiple:
            return [str(info.path) for info in ctrl.value]
        p = ctrl.path()
        return str(p) if p is not None else ""
    return ctrl._selected_key if hasattr(ctrl, "_selected_key") else ctrl.value


def _attached_interface(ctrl: typing.Any) -> Interface | None:
    if isinstance(ctrl, Interface):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, Interface) else None


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
        if sub_iface := _attached_interface(ctrl):
            _collect_usage_placeholders(sub_iface, result)


class SubgroupRegistry:
    """Tracks live subgroup interfaces to detect missing args.interface() calls."""

    def __init__(self) -> None:
        self._refs: dict[str, weakref.ReferenceType[Interface]] = {}

    def register(self, iface: Interface) -> None:
        self._refs = {
            prefix: ref for prefix, ref in self._refs.items() if ref() is not None
        }
        self._refs[iface.option_prefix] = weakref.ref(iface)

    def missing_options(self, controls: typing.Sequence[typing.Any]) -> list[str]:
        covered_ids = {
            id(iface)
            for ctrl in controls
            for iface in [_attached_interface(ctrl)]
            if iface is not None
        }
        missing: list[str] = []
        live_refs: dict[str, weakref.ReferenceType[Interface]] = {}
        for prefix, ref in self._refs.items():
            iface = ref()
            if iface is None:
                continue
            live_refs[prefix] = ref
            if id(iface) in covered_ids:
                continue
            missing.extend(iface.input_options())
        self._refs = live_refs
        return missing


def _ui_dictionary_elements(ctrl: typing.Any) -> dict[str, typing.Any] | None:
    elements = getattr(ctrl, "elements", None)
    return (
        typing.cast(dict[str, typing.Any], elements)
        if isinstance(elements, dict)
        else None
    )


def _default_custom_value(ctrl: typing.Any) -> typing.Any:
    return ctrl.value
