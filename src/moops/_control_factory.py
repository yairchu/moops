import typing

from . import _options, interface


def create_control(
    group: typing.Any,
    iface: interface.Interface,
    cli: _options.InputControl,
) -> typing.Any:
    return group._create_from_cli(cli, _unprefixed_option(iface, cli.option))


def _unprefixed_option(iface: interface.Interface, option: str) -> str:
    if iface.option_prefix and option.startswith(f"{iface.option_prefix}-"):
        return f"--{option[len(iface.option_prefix) :].lstrip('-')}"
    return option
