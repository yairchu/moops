from __future__ import annotations

import typing

T = typing.TypeVar("T")


def attached_interface(ctrl: typing.Any, interface_type: type[T]) -> T | None:
    if isinstance(ctrl, interface_type):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, interface_type) else None


def unprefixed_option(iface: typing.Any, option: str) -> str:
    option_prefix = getattr(iface, "option_prefix", "")
    if option_prefix and option.startswith(f"{option_prefix}-"):
        return f"--{option[len(option_prefix) :].lstrip('-')}"
    return option
