import dataclasses
import typing

import marimo as mo


@dataclasses.dataclass
class Interface:
    """Controls registered by a subgroup's interface, for passing to the parent."""

    controls: tuple[typing.Any]
    notebook_name: str = ""
    option_prefix: str = ""

    def flatten(self) -> typing.Iterator[typing.Any]:
        for ctrl in self.controls:
            if isinstance(ctrl, Interface):
                yield from ctrl.flatten()
            else:
                yield ctrl

    def _mime_(self) -> tuple[str, str]:
        if not self.notebook_name:
            return mo.md("Cli bundle with no notebook name")._mime_()  # type: ignore
        has_exposed = any(
            not ctrl._component_args.get("disabled", False)
            for ctrl in self.flatten()
            if hasattr(ctrl, "_component_args")
        )
        prefix_note = (
            f" (configured by the `--{self.option_prefix}*` options)"
            if has_exposed
            else ""
        )
        return mo.md(
            f"An embedded instance of `{self.notebook_name}`{prefix_note}."
        )._mime_()  # type: ignore
