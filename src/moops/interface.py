import dataclasses
import sys
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _cli_map, _options, _parse
from ._presets import Presets


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any]
    cli_map: _cli_map.CliMap = dataclasses.field(default_factory=_cli_map.CliMap)
    overrides: dict[str, typing.Any] = dataclasses.field(default_factory=lambda: {})
    notebook_name: str = ""
    option_prefix: str = ""
    presets: Presets | None = None

    def __post_init__(self) -> None:
        seen_ids: set[int] = set()
        for ctrl in self.controls:
            if not isinstance(ctrl, Interface) and id(ctrl) in seen_ids:
                raise ValueError("Duplicate control passed to interface")
            seen_ids.add(id(ctrl))

    def validate(self, state: _parse.ParseState) -> typing.Iterator[str]:
        flags: set[str] = set()
        value_options: set[str] = set()
        for cli in self._all_cli_controls():
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

    def help(self, command: str) -> str:
        usage_parts = [
            p for cli in self._all_cli_controls() for p in cli.format_usage_parts()
        ]
        usage_parts.append("[-h/--help]")
        segments = [f"Usage: {command.rsplit('/', 1)[-1]} {' '.join(usage_parts)}"]
        help_lines = [
            line for cli in self._all_cli_controls() for line in cli.format_help_lines()
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

    def _all_cli_controls(self) -> typing.Iterator[_options.CliControl]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._all_cli_controls()
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None and not self._is_overridden(cli):
                    yield cli

    def _key(self, cli: _options.CliControl) -> str:
        option = cli.option[len(self.option_prefix) :].lstrip("-")
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def _is_overridden(self, cli: _options.CliControl) -> bool:
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
            for cli in self._all_cli_controls()
            if cli.option in values
            for arg in cli.format_value(values[cli.option])
        )

    def format_current_command(self, command: str) -> str:
        args = self._current_args()
        name = command.rsplit("/", 1)[-1]
        return f"{name} {args}" if args else name

    def missing_options(self) -> list[str]:
        interface_ids = {id(ctrl) for ctrl in self.controls}
        return [
            cli.option
            for ctrl_id, cli in self.cli_map.items()
            if ctrl_id not in interface_ids
        ]

    def _mime_(self) -> tuple[str, str]:
        if not self.notebook_name:
            return mo.md("Cli bundle with no notebook name")._mime_()  # type: ignore
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
        return mo.md(
            f"An embedded instance of `{self.notebook_name}`{prefix_note}."
        )._mime_()  # type: ignore

    def _flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._flatten()
            else:
                yield ctrl

    def format_help(self, state: _parse.ParseState) -> mo.Html | None:
        help_text = self.help(state.args.command)
        missing_options = self.missing_options()
        if mo.running_in_notebook():
            info = mo.md(
                f"This notebook also works as a script:\n```\n{help_text}\n```\n\n"
                "To run the script with the current values in the notebook use:\n"
                f"```\n{self.format_current_command(state.args.command)}\n```"
            )
            items: list[typing.Any] = [info]
            if self.presets is not None:
                current_args = self._current_args()
                name_input = mo.ui.text(
                    placeholder="preset name",
                    disabled=not current_args,
                )
                save_btn = mo.ui.button(
                    label="Save preset",
                    on_click=lambda _: self.presets.save(  # type: ignore
                        name_input.value, current_args
                    ),
                    disabled=not current_args,
                )
                items.append(
                    mo.hstack(
                        [
                            name_input,
                            save_btn,
                            mo.md(
                                "(preset changed)"
                                if current_args
                                else "(no changes to save)"
                            ),
                        ],
                        justify="start",
                    )
                )
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

        issues = list(self.validate(state))
        if issues:
            print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
            print()

        if state.args.is_help or issues:
            print(help_text)
            sys.exit(1 if issues else 0)
        return None


def _ctrl_value(ctrl: typing.Any) -> typing.Any:
    return ctrl._selected_key if hasattr(ctrl, "_selected_key") else ctrl.value
