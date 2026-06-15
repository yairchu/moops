from __future__ import annotations

import copy
import dataclasses
import typing

import marimo as mo

from . import _interface_utils, _options, _variant, interface


def controls_from(
    group: typing.Any,
    iface: interface.Interface,
    *,
    prefix: str,
    exclude: typing.Iterable[str] = (),
) -> typing.Any:
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
    # Build the dictionary as a VariantAwareDictionary so the mirrored controls
    # stay a reactive UIElement: marimo's UIElementRegistry binds reruns only to
    # globals where isinstance(value, UIElement), so a non-UIElement wrapper
    # would leave the dictionary bound to no name and edits would not propagate.
    # Nested subgroups use it too, so each level can hide its own inactive
    # variant branches via _moops_visible_elements.
    result = VariantAwareDictionary(controls)
    # mo.ui.dictionary clones its elements, so result.elements[key] is a
    # different object than controls[key]. Rebind nested dictionary clones
    # to interfaces that track their own live cloned elements.
    for key, original in controls.items():
        _reattach_interface_to_clone(original, result.elements[key])
    # Use the live clones (result.elements) rather than the originals so
    # that cur_values() reads up-to-date widget values. Apply the mirrored
    # variant metadata to the child group first, so the interface it builds
    # already carries it instead of being mutated afterwards.
    _apply_mirrored_variant_ctx(iface, child, group.option)
    mirrored_iface = child.interface(*result.elements.values())
    result._moops_interface = mirrored_iface  # type: ignore[attr-defined]
    return result


class VariantAwareDictionary(mo.ui.dictionary):
    """A mirrored-controls dictionary with custom display.

    A real ``mo.ui.dictionary`` subclass, so it stays a reactive ``UIElement``
    (cells referencing it rerun when a mirrored control changes). It overrides
    display to show the controls as a plain vertical stack and to hide inactive
    variant branches, instead of marimo's default dictionary layout.
    """

    # Set after construction (controls_from). dictionary.__init__ renders
    # _mime_ before then, so default to None and show all elements until it is.
    _moops_interface: interface.Interface | None = None

    def _clone(self) -> VariantAwareDictionary:
        # Route through UIElement's deepcopy path (not dictionary._clone, which
        # rebuilds a plain dictionary) so the subclass and the _moops_interface
        # attribute set after construction survive cloning.
        return copy.deepcopy(self)

    @property
    def text(self) -> str:
        return self._moops_stacked_display().text

    def _moops_visible_elements(self) -> dict[str, typing.Any]:
        iface = self._moops_interface
        if iface is None:
            return dict(self.elements)
        result: dict[str, typing.Any] = {}
        rendered_variant_groups: set[tuple[str, str]] = set()
        for name, element in self.elements.items():
            sub_iface = interface.attached_interface(element)
            if sub_iface is None or sub_iface.variant_ctx.group_prefix is None:
                result[name] = element
                continue
            assert sub_iface.variant_ctx.selector_option is not None
            group_key = (
                sub_iface.variant_ctx.selector_option,
                sub_iface.variant_ctx.group_prefix,
            )
            if group_key in rendered_variant_groups:
                continue
            rendered_variant_groups.add(group_key)
            active = _active_variant_element(iface, self.elements, sub_iface)
            if active is not None:
                active_name, active_element = active
                result[active_name] = active_element
        return result

    def _moops_stacked_display(self) -> typing.Any:
        return mo.vstack(
            [
                _display_element(element)
                for element in self._moops_visible_elements().values()
            ]
        )

    def _mime_(self) -> typing.Any:
        return self._moops_stacked_display()._mime_()


def _display_element(element: typing.Any) -> typing.Any:
    visible_elements = getattr(element, "_moops_visible_elements", None)
    if callable(visible_elements):
        visible = typing.cast(dict[str, typing.Any], visible_elements())
        return mo.vstack([_display_element(child) for child in visible.values()])
    elements = getattr(element, "elements", None)
    if isinstance(elements, dict) and interface.attached_interface(element) is not None:
        typed_elements = typing.cast(dict[str, typing.Any], elements)
        return mo.vstack([_display_element(child) for child in typed_elements.values()])
    return element


def _active_variant_element(
    root_iface: interface.Interface,
    elements: dict[str, typing.Any],
    variant_iface: interface.Interface,
) -> tuple[str, typing.Any] | None:
    selector_option = variant_iface.variant_ctx.selector_option
    variant_group_prefix = variant_iface.variant_ctx.group_prefix
    selected = interface.selected_value_for_option(root_iface, selector_option)
    if selected is None:
        return None
    selected_key = _variant.key_text(selected)
    for name, element in elements.items():
        sub_iface = interface.attached_interface(element)
        if (
            sub_iface is not None
            and sub_iface.variant_ctx.selector_option == selector_option
            and sub_iface.variant_ctx.group_prefix == variant_group_prefix
            and sub_iface.variant_ctx.key == selected_key
        ):
            return name, element
    return None


def _apply_mirrored_variant_ctx(
    source: interface.Interface,
    child_group: typing.Any,
    mirrored_parent_prefix: str,
) -> None:
    source_ctx = source.variant_ctx
    child_group._variant_ctx = dataclasses.replace(
        child_group._variant_ctx,
        key=source_ctx.key,
        group_prefix=source_ctx.group_prefix,
        selector_parent_prefix=source_ctx.selector_parent_prefix,
        selector_option=_mirrored_selector_option(
            source_ctx.selector_option,
            source_ctx.selector_parent_prefix,
            mirrored_parent_prefix,
        ),
    )


def _mirrored_selector_option(
    selector_option: str | None,
    source_parent_prefix: str,
    mirrored_parent_prefix: str,
) -> str | None:
    if selector_option is None:
        return None
    relative = _interface_utils.strip_option_prefix(
        selector_option, source_parent_prefix
    )
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
    """Create a marimo element from an existing InputControl."""
    display_option = _interface_utils.unprefixed_option(iface, input_control.option)
    opt = group._make_opt(label=None, option=display_option)
    cloned = input_control.with_option(opt.option)
    return group._register_control(opt, cloned, cloned.help_text, None)


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
