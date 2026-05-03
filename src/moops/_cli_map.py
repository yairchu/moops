import typing
import weakref

from . import _options


class CliMap:
    """Maps UI controls to their CLI counterparts."""

    def __init__(self) -> None:
        self._lookup: dict[int, _options.CliControl] = {}

    def register(self, control: typing.Any, cli: _options.CliControl) -> typing.Any:
        ctrl_id = id(control)
        self._lookup[ctrl_id] = cli

        # WeakKeyDictionary would be cleaner but requires hashable keys; marimo
        # controls (e.g. dropdown) define __eq__ without __hash__, so we use
        # finalize() to remove the entry when the control is GC'd instead.
        weakref.finalize(control, self._lookup.pop, ctrl_id, None)

        return control

    def get(self, control: typing.Any) -> _options.CliControl | None:
        return self._lookup.get(id(control))

    def items(self) -> typing.Iterator[tuple[int, _options.CliControl]]:
        yield from self._lookup.items()
