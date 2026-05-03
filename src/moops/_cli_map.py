import typing
import weakref

from . import _options


class CliMap:
    """Maps UI controls to their CLI counterparts."""

    def __init__(self) -> None:
        self._lookup: weakref.WeakKeyDictionary[
            typing.Any, _options.CliControl
        ] = weakref.WeakKeyDictionary()

    def register(self, control: typing.Any, cli: _options.CliControl) -> typing.Any:
        self._lookup[control] = cli
        return control

    def get(self, control: typing.Any) -> _options.CliControl | None:
        return self._lookup.get(control)
