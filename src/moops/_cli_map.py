import typing
import weakref

from . import _options


class CliMap:
    """Maps UI controls to their CLI counterparts."""

    def __init__(self) -> None:
        self._registered: weakref.WeakValueDictionary[str, _options.CliControl] = (
            weakref.WeakValueDictionary()
        )

    def register(self, control: typing.Any, cli: _options.CliControl) -> typing.Any:
        self._registered[cli.option] = cli
        control._moops_cli = cli
        return control

    def get(self, control: typing.Any) -> _options.CliControl | None:
        return getattr(control, "_moops_cli", None)

    def registered_options(self) -> typing.Iterator[_options.CliControl]:
        yield from self._registered.values()
