from __future__ import annotations

import shlex
import typing

from . import _interface_utils, _list_options, interface


def subgroup_leaves(
    template: interface.Interface,
    path: tuple[str, ...] = (),
    bare_prefix: str | None = None,
    variant_selector_bare_option: str | None = None,
    variant_key: str | None = None,
) -> typing.Iterator[_list_options.SubgroupListLeaf]:
    bare_prefix = template.option_prefix if bare_prefix is None else bare_prefix
    for name, ctrl_or_sub in template.iter_controls():
        child_path = (*path, name)
        if isinstance(ctrl_or_sub, interface.Interface):
            child_bare_prefix = _rebase_option(
                ctrl_or_sub.option_prefix, template.option_prefix, bare_prefix
            )
            child_variant_selector = variant_selector_bare_option
            child_variant_key = variant_key
            if ctrl_or_sub.variant_ctx.selector_option is not None:
                child_variant_key = ctrl_or_sub.variant_ctx.key
                assert child_variant_key is not None
                child_bare_prefix = f"{bare_prefix}-{child_variant_key}"
                child_variant_selector = _rebase_option(
                    ctrl_or_sub.variant_ctx.selector_option,
                    template.option_prefix,
                    bare_prefix,
                )
            yield from subgroup_leaves(
                ctrl_or_sub,
                child_path,
                child_bare_prefix,
                child_variant_selector,
                child_variant_key,
            )
        else:
            yield _list_options.SubgroupListLeaf(
                value_path=child_path,
                control=ctrl_or_sub,
                bare_option=_rebase_option(
                    ctrl_or_sub.option, template.option_prefix, bare_prefix
                ),
                variant_selector_bare_option=variant_selector_bare_option,
                variant_key=variant_key,
            )


def _rebase_option(option: str, source_prefix: str, target_prefix: str) -> str:
    relative = _interface_utils.strip_option_prefix(option, source_prefix).lstrip("-")
    return f"{target_prefix}-{relative}"


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
