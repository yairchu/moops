from __future__ import annotations

import typing

T = typing.TypeVar("T")


def attached_interface(ctrl: typing.Any, interface_type: type[T]) -> T | None:
    if isinstance(ctrl, interface_type):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, interface_type) else None


def selected_value_for_option(
    iface: typing.Any,
    selector_option: str | None,
    interface_type: type[T],
    selected_key: typing.Callable[[typing.Any], typing.Any],
) -> typing.Any:
    if selector_option is None:
        return None
    for ctrl in iface.controls:
        sub_iface = attached_interface(ctrl, interface_type)
        if sub_iface is not None:
            selected = selected_value_for_option(
                sub_iface, selector_option, interface_type, selected_key
            )
            if selected is not None:
                return selected
            continue
        input_control = iface.input_map.get(ctrl)
        if input_control is not None and input_control.option == selector_option:
            return selected_key(ctrl)
    return None


def strip_option_prefix(option: str, option_prefix: str) -> str:
    """Return ``option`` relative to ``option_prefix`` as a ``--``-prefixed flag.

    Options that do not carry the prefix are returned unchanged.
    """
    if option_prefix and option.startswith(f"{option_prefix}-"):
        return f"--{option[len(option_prefix) :].lstrip('-')}"
    return option


def unprefixed_option(iface: typing.Any, option: str) -> str:
    return strip_option_prefix(option, getattr(iface, "option_prefix", ""))
