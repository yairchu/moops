import dataclasses
import typing

import marimo as mo
from hypothesis import strategies as st

from . import _cli_map, _options, _parse


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any]
    cli_map: _cli_map.CliMap = dataclasses.field(default_factory=_cli_map.CliMap)
    notebook_name: str = ""
    option_prefix: str = ""

    def validate(self, state: _parse.ParseState) -> typing.Iterator[str]:
        flags: set[str] = set()
        value_options: set[str] = set()
        for cli in self._all_cli_controls():
            flags.update(cli.flags())
            value_options.update(cli.options())
        # TODO: also collect from direct (non-Interface) controls in self.controls
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
        usage_parts = ["[-h/--help]"]  # TODO
        segments = [f"Usage: {command.rsplit('/', 1)[-1]} {' '.join(usage_parts)}"]
        # TODO
        return "\n\n".join(segments)

    @property
    def default(self) -> dict[str, typing.Any]:
        # TODO
        return {}

    def strategy(self) -> st.SearchStrategy[dict[str, typing.Any]]:
        # TODO
        return st.just({})

    def _all_cli_controls(self) -> typing.Iterator[_options.CliControl]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl._all_cli_controls()
            else:
                cli = self.cli_map.get(ctrl)
                if cli is not None:
                    yield cli

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
