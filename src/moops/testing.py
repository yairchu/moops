import types

from . import group, interface


def notebook_interface(module: types.ModuleType) -> interface.Interface:
    _, defs = module.app.run(defs={"args": group.Group.with_overrides({})})
    return defs["interface"]
