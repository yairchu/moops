import types

from . import group


def notebook_args(module: types.ModuleType) -> group.Group:
    args = group.Group.with_overrides({})
    module.app.run(defs={"args": args})
    return args
