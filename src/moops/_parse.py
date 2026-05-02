import dataclasses
import sys

import marimo as mo

help_flags = ["--help", "-h"]


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
            is_negative_num = len(arg) > 1 and arg[0] == "-" and arg[1].isdigit()
            if arg.startswith("-") and not (prev is not None and is_negative_num):
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    result.options[key] = value
                    prev = None
                else:
                    result.options[arg] = None
                    prev = arg
            elif prev is not None and prev.startswith("-"):
                result.options[prev] = arg
                prev = None
            else:
                result.unexpected.append(arg)
        return result
