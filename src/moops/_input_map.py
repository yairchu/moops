import typing
import weakref

from . import _options


class InputMap:
    """Maps UI controls to their input-channel counterparts."""

    def __init__(self) -> None:
        self._registered: weakref.WeakValueDictionary[str, _options.InputControl] = (
            weakref.WeakValueDictionary()
        )
        self._ui_id_options: dict[typing.Any, str] = {}

    def register(
        self, control: typing.Any, input_control: _options.InputControl
    ) -> typing.Any:
        ui_id = getattr(control, "_id", None)
        if ui_id is not None:
            old_option = self._ui_id_options.get(ui_id)
            if old_option is not None and old_option != input_control.option:
                self._registered.pop(old_option, None)
            self._ui_id_options[ui_id] = input_control.option
        self._registered[input_control.option] = input_control
        control._moops_input = input_control
        return control

    def get(self, control: typing.Any) -> _options.InputControl | None:
        return getattr(control, "_moops_input", None)

    def registered_options(self) -> typing.Iterator[_options.InputControl]:
        yield from self._registered.values()
