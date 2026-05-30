from __future__ import annotations

import shlex
import typing

from . import _interface_utils, _list_options, interface


def subgroup_leaves(
    template: interface.Interface,
    path: tuple[str, ...] = (),
    top_template: interface.Interface | None = None,
) -> typing.Iterator[_list_options.SubgroupListLeaf]:
    top = template if top_template is None else top_template
    for name, ctrl_or_sub in template.iter_controls():
        child_path = (*path, name)
        if isinstance(ctrl_or_sub, interface.Interface):
            yield from subgroup_leaves(ctrl_or_sub, child_path, top)
        else:
            yield _list_options.SubgroupListLeaf(
                value_path=child_path,
                control=ctrl_or_sub,
                bare_option=_interface_utils.unprefixed_option(top, ctrl_or_sub.option),
            )


def relative_stem(parent_prefix: str, option: str) -> str:
    return _interface_utils.strip_option_prefix(option, parent_prefix).lstrip("-")


def seed_args_for_subgroup_item(
    leaves: tuple[_list_options.SubgroupListLeaf, ...],
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
        ).format_value(
            _list_options.get_path(item_dict, leaf.value_path, leaf.control.default)
        )
        for token in shlex.split(formatted)
    ]
