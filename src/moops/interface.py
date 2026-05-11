import dataclasses
import html
import pathlib
import sys
import typing
import urllib.parse

import marimo as mo
from hypothesis import strategies as st
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._plugins.ui._impl.file_browser import FileBrowserFileInfo

from . import _input_map, _options, _parse, _query_params
from .presets import Presets


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any]
    cli_map: _input_map.InputMap = dataclasses.field(
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

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self.controls:
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

    def validate(self, state: _parse.ParseState) -> typing.Iterator[str]:
        flags: set[str] = set()
        value_options: set[str] = set()
        for cli in self._all_input_controls():
            flags.update(cli.flags())
            value_options.update(cli.options())
        rendered = flags | value_options
        yield from (v for k, v in state.validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in state.args.unexpected:
            yield f"{unexp_text}{x}"
        for k, v in state.args.options.items():
            if k in flags:
                if v is not None:
                    yield f"{k} does not take a value, but was given: {v}"
            elif k in value_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in _parse.help_flags and k != _parse.interactive_flag:
                yield f"{unexp_text}{k}"

    def help(self) -> str:
        usage_parts = [
            p for cli in self._all_input_controls() for p in cli.format_usage_parts()
        ]
        usage_parts.extend(("[--interactive]", "[-h/--help]"))
        name = self.command.rsplit("/", 1)[-1]
        segments = [f"Usage: {name} {' '.join(usage_parts)}"]
        help_lines = [
            line
            for cli in self._all_input_controls()
            for line in cli.format_help_lines()
        ]
        if help_lines:
            segments.append("\n".join(help_lines))
        return "\n\n".join(segments)

    @property
    def default(self) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                prefix = ctrl.option_prefix.lstrip("-")
                result[prefix] = ctrl.default
            else:
                cli = self.cli_map.get(ctrl)
                if (
                    cli is not None
                    and not self._is_overridden(cli)
                    and hasattr(cli, "default")
                ):
                    result[self._key(cli)] = cli.default  # type: ignore
        return result

    def strategy(self) -> st.SearchStrategy[dict[str, typing.Any]]:
        strategies: dict[str, st.SearchStrategy[typing.Any]] = {}
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                prefix = ctrl.option_prefix.lstrip("-")
                strategies[prefix] = ctrl.strategy()
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None and not self._is_overridden(cli):
                    strategies[self._key(cli)] = cli.strategy()
        return st.fixed_dictionaries(strategies).map(
            lambda d: {k: v for k, v in d.items() if v is not None}
        )

    def _all_input_controls(self) -> typing.Iterator[_options.InputControl]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._all_input_controls()
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None and not self._is_overridden(cli):
                    yield cli

    def _key(self, cli: _options.InputControl) -> str:
        option = cli.option[len(self.option_prefix) :].lstrip("-")
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def _is_overridden(self, cli: _options.InputControl) -> bool:
        return self._key(cli) in self.overrides

    def cur_values(self) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                result.update(ctrl.cur_values())
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None and not self._is_overridden(cli):
                    result[cli.option] = _ctrl_value(ctrl)
        return result

    def _current_args(self) -> str:
        values = self.cur_values()
        return " ".join(
            arg
            for cli in self._all_input_controls()
            if cli.option in values
            for arg in cli.format_value(values[cli.option])
        )

    def missing_options(self) -> list[str]:
        covered = {
            cli.option
            for ctrl in self.controls
            if not isinstance(ctrl, Interface)
            for cli in [self.cli_map.get(ctrl)]
            if cli is not None
        }
        return [
            cli.option
            for cli in self.cli_map.registered_options()
            if cli.option not in covered
        ]

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
            return mo.md("Cli bundle with no notebook name")
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
                continue
            cli = self.cli_map.get(ctrl)
            if cli is None:
                continue
            value = cli.format_query_value(_ctrl_value(ctrl))
            if value is not None:
                values[_query_params.escape_url_key(self._key(cli))] = value
        return values

    def _root_panel(self) -> mo.Html:
        args = self._current_args()
        name = self.command.rsplit("/", 1)[-1]
        current_command = f"{name} {args}" if args else name
        items: list[typing.Any] = [
            mo.callout(
                mo.md(
                    f"This notebook also works as a script:\n```\n{self.help()}\n```\n"
                    "To run the script with the current values in the notebook use:\n"
                    f"```\n{current_command}\n```"
                ),
                "info",
            )
        ]
        if self._presets_ui is not None:
            items.append(self._presets_ui.layout(args))
        missing_options = self.missing_options()
        if missing_options:
            items.append(
                mo.callout(
                    mo.md(
                        "Missing options: "
                        f"{', '.join(f'`{opt}`' for opt in missing_options)}"
                    ),
                    "warn",
                )
            )
        return mo.vstack(items)

    def _select_preset(self, preset: str | None) -> None:
        assert self.presets is not None
        self.presets.select("" if preset is None else preset)
        if preset is None:
            self._clear_query_params()

    def _clear_query_params(self) -> None:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                ctrl._clear_query_params()
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None:
                    self.query_params.clear(self._key(cli))

    def _flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._flatten()
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


class FileBrowserWithInitialSelection(mo.ui.file_browser):
    """Extends mo.ui.file_browser with a CLI path fallback when no file is selected."""

    def __init__(self, default: str, **kwargs: typing.Any) -> None:
        self._default = default
        super().__init__(**kwargs)

    @property
    def value(self) -> list[FileBrowserFileInfo]:  # type: ignore[override]
        if browser_value := list(super().value):
            return browser_value
        p = pathlib.Path(self._default)
        return [
            FileBrowserFileInfo(
                id=self._default, path=p, name=p.name, is_directory=p.is_dir()
            )
        ]

    @value.setter
    def value(self, value: typing.Any) -> None:
        del value
        raise RuntimeError("Setting the value of a UIElement is not allowed.")

    def _mime_(self) -> tuple[str, str]:  # type: ignore[override]
        return mo.vstack(
            [
                mo.Html(super()._mime_()[1]),
                mo.callout(
                    mo.md(
                        "marimo's file browser does not support "
                        f"an initial selection — falling back to `{self._default}`"
                    ),
                    kind="info",
                ),
            ]
        )._mime_()  # type: ignore


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
        p = ctrl.path()
        return str(p) if p is not None else ""
    return ctrl._selected_key if hasattr(ctrl, "_selected_key") else ctrl.value


def _default_custom_value(ctrl: typing.Any) -> typing.Any:
    return ctrl.value
