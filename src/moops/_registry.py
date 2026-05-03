import typing

from . import _parse


class ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(self, controls: tuple[typing.Any]) -> None:
        self.flags: set[str] = set()
        self.value_options: set[str] = set()
        # TODO

    def validate(
        self, args: _parse.ParsedArgs, validation_errors: dict[str, str]
    ) -> typing.Iterator[str]:
        rendered = self.flags | self.value_options
        yield from (v for k, v in validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in args.unexpected:
            yield f"{unexp_text}{x}"
        for k, v in args.options.items():
            if k in self.flags:
                if v is not None:
                    yield f"{k} does not take a value, but was given: {v}"
            elif k in self.value_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in _parse.help_flags:
                yield f"{unexp_text}{k}"
