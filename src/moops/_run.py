import types
import typing

from . import interface, group


def run(module: types.ModuleType, **kwargs: typing.Any) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable.

    Keyword arguments override control values by label name
    (lowercased, spaces replaced with underscores). For example, a
    text area labelled "Input text" is overridden with input_text="...".
    All controls are overridable, including those not passed to render_cli.
    """
    args = object.__new__(group.Group)
    args._state = group._GroupState(args=interface._ParsedArgs.parse(["run"]))
    args._overrides = kwargs
    args._option_prefix = ""

    _, defs = module.app.run(defs={"args": args})
    return defs.get("result")
