import dataclasses
import math

help_flags = ["--help", "-h"]


@dataclasses.dataclass
class _ParsedArgs:
    command: str
    options: dict[str, str | None]
    unexpected: list[str]

    @property
    def is_help(self) -> bool:
        return any(x in self.options for x in help_flags)

    @classmethod
    def parse(cls, args: list[str]) -> "_ParsedArgs":
        """Parse command line arguments into flags and options."""

        cmd, *rest = args
        result = cls(command=cmd, options={}, unexpected=[])
        prev = None
        for arg in rest:
            if arg.startswith("-"):
                if "=" in arg:
                    prefix, value = arg.split("=", 1)
                    result.options[prefix] = value
                    prev = None
                else:
                    result.options[arg] = None
            elif prev is not None and prev.startswith("-"):
                result.options[prev] = arg
            else:
                result.unexpected.append(arg)
            prev = arg
        return result

    def get_num(self, key: str) -> float | int | None | str:
        """Parse number or return error message on failure."""
        value = self.options.get(key)
        if value is None:
            return None
        try:
            value = float(value)
        except ValueError:
            return f"Option {key} expects a number, got: {value!r}"
        if math.isfinite(value) and value == int(value):
            return int(value)
        return value
