import dataclasses
import sys
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _input_map, _options, _parse
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
    option_prefix: str = ""
    presets: Presets | None = None
    command: str = ""

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self.controls:
            if not isinstance(ctrl, Interface) and id(ctrl) in seen_ids:
                raise ValueError("Duplicate control passed to interface")
            seen_ids.add(id(ctrl))
        self._presets_ui = (
            _PresetsUI(self.presets, self._current_args)
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
            elif k not in _parse.help_flags:
                yield f"{unexp_text}{k}"

    def help(self) -> str:
        usage_parts = [
            p for cli in self._all_input_controls() for p in cli.format_usage_parts()
        ]
        usage_parts.append("[-h/--help]")
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
        has_exposed = any(
            not ctrl._component_args.get("disabled", False)
            for ctrl in self._flatten()
            if hasattr(ctrl, "_component_args")
        )
        prefix_note = (
            f" (configured by the `{self.option_prefix}` options)"
            if has_exposed
            else ""
        )
        return mo.md(f"An embedded instance of `{self.notebook_name}`{prefix_note}.")

    def _root_panel(self) -> mo.Html:
        args = self._current_args()
        name = self.command.rsplit("/", 1)[-1]
        current_command = f"{name} {args}" if args else name
        info = mo.md(
            f"This notebook also works as a script:\n```\n{self.help()}\n```\n\n"
            "To run the script with the current values in the notebook use:\n"
            f"```\n{current_command}\n```"
        )
        items: list[typing.Any] = [info]
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

    def _flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._flatten()
            else:
                yield ctrl


class _PresetsUI:
    def __init__(self, presets: Presets, get_args: typing.Callable[[], str]) -> None:
        self._presets = presets
        self._name_input = mo.ui.text(placeholder="preset name")
        self._save_btn = mo.ui.button(
            label="Save preset",
            on_click=lambda _: presets.save(self._name_input.value, get_args()),
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
            value=self._presets.get_current(),
            on_change=self._presets.select,
        )
        return mo.hstack(
            [
                self._dropdown,
                *(
                    []
                    if args == self._presets.selected_args
                    else [self._name_input, self._save_btn]
                ),
            ],
            justify="start",
        )


def _ctrl_value(ctrl: typing.Any) -> typing.Any:
    return ctrl._selected_key if hasattr(ctrl, "_selected_key") else ctrl.value
