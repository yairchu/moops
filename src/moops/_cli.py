import dataclasses
import marimo as mo
import math
import sys

help_flags = ["--help", "-h"]


@dataclasses.dataclass
class _ParseError:
    message: str


@dataclasses.dataclass
class _DropdownValue:
    value: str | None


@dataclasses.dataclass
class _CliBundle:
    """Controls registered by a subgroup's render_cli, for passing to the parent."""

    controls: tuple


@dataclasses.dataclass
class _ParsedArgs:
    command: str
    options: dict[str, str | None]
    unexpected: list[str]

    @property
    def is_help(self) -> bool:
        return any(x in self.options for x in help_flags)

    @classmethod
    def parse(cls, args: list[str] | None) -> "_ParsedArgs":
        """Parse command line arguments into flags and options."""

        if args is None:
            args = sys.argv
            if mo.running_in_notebook():
                # When notebooks embed other notebooks, the outer notebook is the last argument in sys.argv
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

    def get_dropdown(
        self, option: str, keys: list[str], no_flag: str | None
    ) -> _DropdownValue | _ParseError | None:
        """Returns the selected value, a parse error, or None if not provided."""
        if no_flag and no_flag in self.options:
            if option in self.options:
                return _ParseError(f"Cannot use both {option} and {no_flag}")
            return _DropdownValue(None)
        raw = self.options.get(option)
        if raw is None:
            return None
        if raw not in keys:
            return _ParseError(f"Option {option} must be one of {keys!r}, got: {raw!r}")
        return _DropdownValue(raw)

    def get_text_area(self, option: str, stdin_flag: str) -> str | _ParseError | None:
        """Returns stdin content, a parse error, or None if not provided."""
        if mo.running_in_notebook() or stdin_flag not in self.options:
            return None
        if option in self.options:
            return _ParseError(f"Cannot use both {option} and {stdin_flag}")
        return sys.stdin.read() if self.options[stdin_flag] is None else None

    def get_num(self, key: str) -> float | int | _ParseError | None:
        """Parse number or return a parse error."""
        value = self.options.get(key)
        if value is None:
            return None
        try:
            value = float(value)
        except ValueError:
            return _ParseError(f"Option {key} expects a number, got: {value!r}")
        return int(value) if math.isfinite(value) and value == int(value) else value
