from __future__ import annotations

import shlex
import typing

from . import _options, interface


def subgroup_leaves(
    template: interface.Interface,
    path: tuple[str, ...] = (),
    top_template: interface.Interface | None = None,
) -> typing.Iterator[_options.SubgroupListLeaf]:
    top = template if top_template is None else top_template
    for name, ctrl_or_sub in template.iter_controls():
        child_path = (*path, name)
        if isinstance(ctrl_or_sub, interface.Interface):
            yield from subgroup_leaves(ctrl_or_sub, child_path, top)
        else:
            yield _options.SubgroupListLeaf(
                value_path=child_path,
                control=ctrl_or_sub,
                bare_option=unprefixed_option(top, ctrl_or_sub.option),
            )


def unprefixed_option(iface: interface.Interface, option: str) -> str:
    if iface.option_prefix and option.startswith(f"{iface.option_prefix}-"):
        return f"--{option[len(iface.option_prefix) :].lstrip('-')}"
    return option


def relative_stem(parent_prefix: str, option: str) -> str:
    if parent_prefix and option.startswith(f"{parent_prefix}-"):
        return option[len(parent_prefix) :].lstrip("-")
    return option.lstrip("-")


def attached_interface(ctrl: typing.Any) -> interface.Interface | None:
    if isinstance(ctrl, interface.Interface):
        return ctrl
    iface = getattr(ctrl, "_moops_interface", None)
    return iface if isinstance(iface, interface.Interface) else None


def value_at_path(
    source: dict[str, typing.Any], path: tuple[str, ...], default: typing.Any
) -> typing.Any:
    current: typing.Any = source
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = typing.cast(dict[str, typing.Any], current)[part]
    return current


def seed_args_for_subgroup_item(
    leaves: tuple[_options.SubgroupListLeaf, ...],
    *,
    list_option: str,
    item_prefix: str,
    item_dict: dict[str, typing.Any],
) -> list[str]:
    return [
        token
        for leaf in leaves
        for rel_option in [leaf.control.option[len(list_option) :].lstrip("-")]
        for formatted in leaf.control.with_option(
            f"{item_prefix}-{rel_option}"
        ).format_value(value_at_path(item_dict, leaf.value_path, leaf.control.default))
        for token in shlex.split(formatted)
    ]
