from __future__ import annotations

import copy
import typing

import marimo as mo

from . import _options, interface


def controls_from(
    group: typing.Any,
    iface: interface.Interface,
    *,
    prefix: str,
    exclude: typing.Iterable[str] = (),
    _wrap_display: bool = True,
) -> typing.Any:
    """Create a subgroup of controls mirroring another notebook's interface."""
    child = group.subgroup(prefix)
    excluded = set(exclude)
    controls: dict[str, typing.Any] = {
        name: (
            controls_from(child, ctrl_or_sub, prefix=name, _wrap_display=False)
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
    mirrored_iface = child.interface(*result.elements.values())
    _copy_variant_metadata(iface, mirrored_iface, group.option)
    result._moops_interface = mirrored_iface  # type: ignore[attr-defined]
    return VariantAwareDictionary(result) if _wrap_display else result


class VariantAwareDictionary:
    """Display proxy for mirrored controls.

    It keeps the dictionary value/element API, but displays controls as a plain
    vertical stack and hides inactive variant branches.
    """

    def __init__(self, dictionary: mo.ui.dictionary) -> None:
        self._dictionary = dictionary
        self._id = getattr(dictionary, "_id", f"variant-dict-{id(self)}")
        self._moops_interface = typing.cast(typing.Any, dictionary)._moops_interface

    @property
    def value(self) -> typing.Any:
        return self._dictionary.value

    @property
    def elements(self) -> dict[str, typing.Any]:
        return self._dictionary.elements

    def _moops_visible_elements(self) -> dict[str, typing.Any]:
        iface = typing.cast(interface.Interface, self._moops_interface)
        result: dict[str, typing.Any] = {}
        rendered_variant_groups: set[tuple[str, str]] = set()
        for name, element in self.elements.items():
            sub_iface = _attached_interface(element)
            if sub_iface is None or sub_iface.variant_group_prefix is None:
                result[name] = element
                continue
            assert sub_iface.variant_selector_option is not None
            group_key = (
                sub_iface.variant_selector_option,
                sub_iface.variant_group_prefix,
            )
            if group_key in rendered_variant_groups:
                continue
            rendered_variant_groups.add(group_key)
            active = _active_variant_element(iface, self.elements, sub_iface)
            if active is not None:
                active_name, active_element = active
                result[active_name] = active_element
        return result

    def _mime_(self) -> typing.Any:
        visible = mo.vstack(
            [
                _display_element(element)
                for element in self._moops_visible_elements().values()
            ]
        )
        return typing.cast(typing.Any, visible)._mime_()

    def __deepcopy__(self, memo: dict[int, typing.Any]) -> VariantAwareDictionary:
        return type(self)(copy.deepcopy(self._dictionary, memo))

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._dictionary, name)


def _display_element(element: typing.Any) -> typing.Any:
    visible_elements = getattr(element, "_moops_visible_elements", None)
    if callable(visible_elements):
        visible = typing.cast(dict[str, typing.Any], visible_elements())
        return mo.vstack([_display_element(child) for child in visible.values()])
    elements = getattr(element, "elements", None)
    if isinstance(elements, dict) and _attached_interface(element) is not None:
        typed_elements = typing.cast(dict[str, typing.Any], elements)
        return mo.vstack([_display_element(child) for child in typed_elements.values()])
    return element


def _active_variant_element(
    root_iface: interface.Interface,
    elements: dict[str, typing.Any],
    variant_iface: interface.Interface,
) -> tuple[str, typing.Any] | None:
    selector_option = variant_iface.variant_selector_option
    variant_group_prefix = variant_iface.variant_group_prefix
    selected = _selected_value_for_option(root_iface, selector_option)
    if selected is None:
        return None
    selected_key = (
        str(selected).lower() if isinstance(selected, bool) else str(selected)
    )
    for name, element in elements.items():
        sub_iface = _attached_interface(element)
        if (
            sub_iface is not None
            and sub_iface.variant_selector_option == selector_option
            and sub_iface.variant_group_prefix == variant_group_prefix
            and sub_iface.variant_key == selected_key
        ):
            return name, element
    return None


def _selected_value_for_option(
    iface: interface.Interface, selector_option: str | None
) -> typing.Any:
    if selector_option is None:
        return None
    for ctrl in iface.controls:
        sub_iface = _attached_interface(ctrl)
        if sub_iface is not None:
            selected = _selected_value_for_option(sub_iface, selector_option)
            if selected is not None:
                return selected
            continue
        input_control = iface.input_map.get(ctrl)
        if input_control is not None and input_control.option == selector_option:
            if hasattr(ctrl, "_selected_key"):
                return ctrl._selected_key
            return ctrl.value
    return None


def _attached_interface(ctrl: typing.Any) -> interface.Interface | None:
    if isinstance(ctrl, interface.Interface):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, interface.Interface) else None


def _copy_variant_metadata(
    source: interface.Interface,
    target: interface.Interface,
    mirrored_parent_prefix: str,
) -> None:
    target.variant_key = source.variant_key
    target.variant_group_prefix = source.variant_group_prefix
    target.variant_selector_parent_prefix = source.variant_selector_parent_prefix
    target.variant_selector_option = _mirrored_selector_option(
        source.variant_selector_option,
        source.variant_selector_parent_prefix,
        mirrored_parent_prefix,
    )


def _mirrored_selector_option(
    selector_option: str | None,
    source_parent_prefix: str,
    mirrored_parent_prefix: str,
) -> str | None:
    if selector_option is None:
        return None
    relative = selector_option
    if source_parent_prefix and selector_option.startswith(f"{source_parent_prefix}-"):
        relative = f"--{selector_option[len(source_parent_prefix) :].lstrip('-')}"
    return (
        f"{mirrored_parent_prefix}-{relative.lstrip('-')}"
        if mirrored_parent_prefix
        else relative
    )


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
    cloned = input_control.with_option(opt.option)
    return group._register_control(opt, cloned, cloned.help_text, None)


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
