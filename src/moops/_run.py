import types
import typing

from . import _cli, group


def run(module: types.ModuleType, **kwargs: typing.Any) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable."""
    args = object.__new__(group.Group)
    args._state = group._GroupState(args=_cli._ParsedArgs.parse(["run"]))
    args._overrides = kwargs
    args._option_prefix = ""

    _, defs = module.app.run(defs={"args": args})
    return defs.get("result")
