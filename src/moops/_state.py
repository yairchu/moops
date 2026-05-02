import dataclasses
import sys
import typing
import warnings
import weakref

import marimo as mo

from . import _options, _parse, interface


@dataclasses.dataclass
class GroupState:
    args: _parse.ParsedArgs
    validation_errors: dict[str, str] = dataclasses.field(default_factory=lambda: {})
    control_meta: dict[int, _options.ControlMeta] = dataclasses.field(
        default_factory=lambda: {}
    )

    def register(self, control: typing.Any, meta: _options.ControlMeta) -> typing.Any:
        meta.control_ref = weakref.ref(control)
        self.control_meta[id(control)] = meta
        return control

    def interface_info(self, controls: tuple[typing.Any]) -> mo.Html | None:
        registry = _options.ControlRegistry(controls, self.control_meta)

        show_help = self.args.is_help
        has_errors = False
        if not mo.running_in_notebook():
            issues = list(registry.validate(self.args, self.validation_errors))
            if issues:
                print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
                print()
                show_help = True
                has_errors = True

        help_text = registry.format_help(self.args.command)
        missing_options = self._missing_from_interface(controls)
        if mo.running_in_notebook():
            info = mo.md(
                f"This notebook also works as a script:\n```\n{help_text.strip()}\n```"
            )
            return (
                mo.vstack(
                    [
                        info,
                        mo.callout(
                            mo.md(
                                f"Controls missing from interface: "
                                f"`{', '.join(missing_options)}`"
                            ),
                            "warn",
                        ),
                    ]
                )
                if missing_options
                else info
            )
        if show_help:
            print(help_text)
            sys.exit(1 if has_errors else 0)

        if missing_options:
            warnings.warn(
                "Controls registered with this Group but not passed to interface(): "
                + ", ".join(missing_options),
                stacklevel=3,
            )

        return None

    def _missing_from_interface(self, controls: tuple[typing.Any]) -> list[str]:
        interface_ids = {id(ctrl) for ctrl in interface.Interface(controls).flatten()}
        return [
            meta.cli.opt.option
            for ctrl_id, meta in self.control_meta.items()
            if meta.control_ref is not None
            and meta.control_ref() is not None
            and ctrl_id not in interface_ids
        ]

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if mo.running_in_notebook():
            return mo.md(text)
        if self.args.is_help:
            return None
        text = text.strip()
        if text.startswith("```\n") and text.endswith("\n```"):
            text = text[4:-4]
        elif text.startswith("`") and text.endswith("`"):
            text = text[1:-1]
        print(f"{text}\n")
        return None
