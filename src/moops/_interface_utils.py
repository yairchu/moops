from __future__ import annotations

import typing

T = typing.TypeVar("T")


def attached_interface(ctrl: typing.Any, interface_type: type[T]) -> T | None:
    if isinstance(ctrl, interface_type):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, interface_type) else None


def strip_option_prefix(option: str, option_prefix: str) -> str:
    """Return ``option`` relative to ``option_prefix`` as a ``--``-prefixed flag.

    Options that do not carry the prefix are returned unchanged.
    """
    if option_prefix and option.startswith(f"{option_prefix}-"):
        return f"--{option[len(option_prefix) :].lstrip('-')}"
    return option


def unprefixed_option(iface: typing.Any, option: str) -> str:
    return strip_option_prefix(option, getattr(iface, "option_prefix", ""))
