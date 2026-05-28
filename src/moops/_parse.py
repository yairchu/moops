import dataclasses
import sys

import marimo as mo

help_flags = ["--help", "-h"]
interactive_flag = "--interactive"


@dataclasses.dataclass
class ParsedArgs:
    options: dict[str, list[str | None]]
    unexpected: list[str]
    raw_args: list[str] = dataclasses.field(default_factory=list[str])

    def values_for(self, option: str) -> list[str | None]:
        return self.options.get(option, [])

    def value_for(self, option: str) -> str | None:
        values = self.values_for(option)
        return values[-1] if values else None

    def has(self, option: str) -> bool:
        return option in self.options

    @property
    def is_help(self) -> bool:
        return any(self.has(x) for x in help_flags)

    @property
    def is_interactive(self) -> bool:
        return self.has(interactive_flag)

    @classmethod
    def from_options(cls, args: list[str]) -> "ParsedArgs":
        """Parse a pre-tokenized list of options (no command name)."""

        options: dict[str, list[str | None]] = {}
        unexpected: list[str] = []
        prev = None
        for arg in args:
            is_negative_num = len(arg) > 1 and arg[0] == "-" and arg[1].isdigit()
            if arg.startswith("-") and not (prev is not None and is_negative_num):
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    options.setdefault(key, []).append(value)
                    prev = None
                else:
                    options.setdefault(arg, []).append(None)
                    prev = arg
            elif prev is not None and prev.startswith("-"):
                options[prev][-1] = arg
                prev = None
            else:
                unexpected.append(arg)
        return cls(options=options, unexpected=unexpected, raw_args=args)


@dataclasses.dataclass
class ParseState:
    """Shared mutable state between a Group and all its subgroups."""

    args: ParsedArgs
    validation_errors: dict[str, str] = dataclasses.field(
        default_factory=dict[str, str]
    )
    failed_validation: bool = False


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
