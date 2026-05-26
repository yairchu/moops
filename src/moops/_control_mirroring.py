from __future__ import annotations

import dataclasses
import typing

import marimo as mo

from . import _options, interface


def controls_from(
    group: typing.Any,
    iface: interface.Interface,
    *,
    prefix: str,
    exclude: typing.Iterable[str] = (),
) -> mo.ui.dictionary:
    """Create a subgroup of controls mirroring another notebook's interface."""
    child = group.subgroup(prefix)
    excluded = set(exclude)
    controls: dict[str, typing.Any] = {
        name: (
            controls_from(child, ctrl_or_sub, prefix=name)
            if isinstance(ctrl_or_sub, interface.Interface)
            else _create_control(child, iface, ctrl_or_sub)
        )
        for name, ctrl_or_sub in iface.iter_controls()
        if name not in excluded
    }
    result = mo.ui.dictionary(controls)
    # mo.ui.dictionary clones its elements, so result.elements[key] is a
    # different object than controls[key]. Rebind nested dictionary clones
    # to interfaces that track their own live cloned elements.
    for key, original in controls.items():
        _reattach_interface_to_clone(original, result.elements[key])
    # Use the live clones (result.elements) rather than the originals so
    # that cur_values() reads up-to-date widget values.
    result._moops_interface = child.interface(*result.elements.values())  # type: ignore[attr-defined]
    return result


def _create_control(
    group: typing.Any,
    iface: interface.Interface,
    input_control: _options.InputControl,
) -> typing.Any:
    return _create_from_input_control(
        group, input_control, _unprefixed_option(iface, input_control.option)
    )


def _create_from_input_control(
    group: typing.Any,
    input_control: _options.InputControl,
    display_option: str,
) -> typing.Any:
    """Create a marimo element from an existing InputControl."""
    opt = group._make_opt(label=None, option=display_option)
    cloned = dataclasses.replace(input_control, option=opt.option)
    value = group._get_value(cloned, getattr(cloned, "default", None))
    ctrl_kwargs = group._control_kwargs(opt, cloned, cloned.help_text, None)
    return group._input_map.register(
        cloned.create_marimo_element(value, **ctrl_kwargs),
        cloned,
    )


def _unprefixed_option(iface: interface.Interface, option: str) -> str:
    if iface.option_prefix and option.startswith(f"{iface.option_prefix}-"):
        return f"--{option[len(iface.option_prefix) :].lstrip('-')}"
    return option


def _reattach_interface_to_clone(original: typing.Any, clone: typing.Any) -> None:
    moops_iface = getattr(original, "_moops_interface", None)
    if not isinstance(moops_iface, interface.Interface):
        return
    original_elements = getattr(original, "elements", None)
    clone_elements = getattr(clone, "elements", None)
    if isinstance(original_elements, dict) and isinstance(clone_elements, dict):
        typed_original_elements = typing.cast(dict[str, typing.Any], original_elements)
        typed_clone_elements = typing.cast(dict[str, typing.Any], clone_elements)
        for key, original_child in typed_original_elements.items():
            if key in typed_clone_elements:
                _reattach_interface_to_clone(original_child, typed_clone_elements[key])
        controls = tuple(typed_clone_elements.values())
    else:
        controls = moops_iface.controls
    moops_iface.controls = controls
    clone._moops_interface = moops_iface
