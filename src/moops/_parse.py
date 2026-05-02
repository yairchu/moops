import dataclasses
import sys

import marimo as mo

help_flags = ["--help", "-h"]


@dataclasses.dataclass
class ParseError:
    message: str


@dataclasses.dataclass
class DropdownValue:
    value: str | None


@dataclasses.dataclass
class ParsedArgs:
    command: str
    options: dict[str, str | None]
    unexpected: list[str]

    @property
    def is_help(self) -> bool:
        return any(x in self.options for x in help_flags)

    @classmethod
    def parse(cls, args: list[str] | None) -> "ParsedArgs":
        """Parse command line arguments into flags and options."""

        if args is None:
            args = sys.argv
            if mo.running_in_notebook():
                # When notebooks embed other notebooks,
                # the outer notebook is the last argument in sys.argv
                args = args[-1:]

        cmd, *rest = args
        result = cls(command=cmd, options={}, unexpected=[])
        prev = None
        for arg in rest:
            if arg.startswith("-"):
                if "=" in arg:
                    prefix, value = arg.split("=", 1)
                    result.options[prefix] = value
                else:
                    result.options[arg] = None
            elif prev is not None and prev.startswith("-"):
                result.options[prev] = arg
            else:
                result.unexpected.append(arg)
            prev = None if "=" in arg else arg
        return result
