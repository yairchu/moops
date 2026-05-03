import dataclasses
import typing

from . import _options


@dataclasses.dataclass
class CliMap:
    """Maps UI controls to their CLI counterparts."""

    _lookup: dict[int, _options.CliControl] = dataclasses.field(
        default_factory=dict[int, _options.CliControl]
    )

    def register(self, control: typing.Any, cli: _options.CliControl) -> typing.Any:
        self._lookup[id(control)] = cli
        return control

    def get(self, control: typing.Any) -> _options.CliControl | None:
        return self._lookup.get(id(control))
