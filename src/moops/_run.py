import types
import typing

from . import group


def run(module: types.ModuleType, **kwargs: typing.Any) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable.

    Keyword arguments override control values by label name
    (lowercased, spaces replaced with underscores). For example, a
    text area labelled "Input text" is overridden with input_text="...".
    All controls are overridable, including those not passed to interface.
    """
    args = group.Group.with_overrides(kwargs)

    _, defs = module.app.run(defs={"args": args})
    return defs.get("result")
