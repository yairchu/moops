import typing

from . import _options, interface


def create_control(
    group: typing.Any,
    iface: interface.Interface,
    input_control: _options.InputControl,
) -> typing.Any:
    return group._create_from_input_control(
        input_control, _unprefixed_option(iface, input_control.option)
    )


def _unprefixed_option(iface: interface.Interface, option: str) -> str:
    if iface.option_prefix and option.startswith(f"{iface.option_prefix}-"):
        return f"--{option[len(iface.option_prefix) :].lstrip('-')}"
    return option
