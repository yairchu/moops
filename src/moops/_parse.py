import dataclasses
import sys

import marimo as mo

help_flags = ["--help", "-h"]


@dataclasses.dataclass
class ParsedArgs:
    options: dict[str, str | None]
    unexpected: list[str]

    @property
    def is_help(self) -> bool:
        return any(x in self.options for x in help_flags)

    @classmethod
    def from_options(cls, args: list[str]) -> "ParsedArgs":
        """Parse a pre-tokenized list of options (no command name)."""

        options: dict[str, str | None] = {}
        unexpected: list[str] = []
        prev = None
        for arg in args:
            is_negative_num = len(arg) > 1 and arg[0] == "-" and arg[1].isdigit()
            if arg.startswith("-") and not (prev is not None and is_negative_num):
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    options[key] = value
                    prev = None
                else:
                    options[arg] = None
                    prev = arg
            elif prev is not None and prev.startswith("-"):
                options[prev] = arg
                prev = None
            else:
                unexpected.append(arg)
        return cls(options=options, unexpected=unexpected)


@dataclasses.dataclass
class ParseState:
    """Shared mutable state between a Group and all its subgroups."""

    args: ParsedArgs
    validation_errors: dict[str, str] = dataclasses.field(
        default_factory=dict[str, str]
    )


def split_argv(args: list[str] | None) -> tuple[str, list[str]]:
    """Split argv-shaped input into (command, options)."""
    if args is None:
        args = sys.argv
        if mo.running_in_notebook():
            # When notebooks embed other notebooks,
            # the outer notebook is the last argument in sys.argv
            args = args[-1:]
    cmd, *rest = args
    return cmd, rest
