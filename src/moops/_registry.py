import typing

from . import _options, _parse, interface


class ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(
        self, controls: tuple[typing.Any], control_meta: dict[int, _options.ControlMeta]
    ) -> None:
        self._controls: list[_options.CliControl] = []
        self.flags: set[str] = set()
        self.value_options: set[str] = set()
        self._populate(controls, control_meta)

    def _populate(
        self, controls: tuple[typing.Any], control_meta: dict[int, _options.ControlMeta]
    ) -> None:
        seen: set[str] = set()
        for ctrl in controls:
            if isinstance(ctrl, interface.Interface):
                self._populate(ctrl.controls, ctrl.control_meta)
                continue
            meta = control_meta.get(id(ctrl))
            if meta is None:
                continue
            if meta.cli.option in seen:
                raise ValueError(
                    f"Option {meta.cli.option!r} passed to interface() more than once"
                )
            seen.add(meta.cli.option)
            if meta.overridden:
                continue
            self.value_options.update(meta.cli.options())
            self.flags.update(meta.cli.flags())
            self._controls.append(meta.cli)

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
