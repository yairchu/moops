import typing
import weakref

from . import _options


class InputMap:
    """Maps UI controls to their input-channel counterparts."""

    def __init__(self) -> None:
        self._registered: weakref.WeakValueDictionary[str, _options.InputControl] = (
            weakref.WeakValueDictionary()
        )

    def register(self, control: typing.Any, cli: _options.InputControl) -> typing.Any:
        self._registered[cli.option] = cli
        control._moops_input = cli
        return control

    def get(self, control: typing.Any) -> _options.InputControl | None:
        return getattr(control, "_moops_input", None)

    def registered_options(self) -> typing.Iterator[_options.InputControl]:
        yield from self._registered.values()
