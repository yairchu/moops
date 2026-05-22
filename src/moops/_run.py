import types
import typing

from . import group, workarounds
from .interface import Interface


def interface_of(module: types.ModuleType) -> Interface:
    """Return a notebook's Interface without running its computation.

    Notebooks can skip heavy work during interface queries::

        mo.stop(args.is_interface_query)

    Useful for surfacing a notebook's controls into a parent notebook without
    embedding it, e.g. when calling the notebook in a loop via ``moops.run()``.
    """
    args = group.Group.for_interface_query()
    _, defs = workarounds.run_in_thread_if_in_async(module.app.run, defs={"args": args})
    return defs["interface"]


def run(module: types.ModuleType, **kwargs: typing.Any) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable.

    Keyword arguments override control values by option name
    (leading dashes removed and dashes replaced with underscores). For example,
    a text area with option "--input-text" is overridden with input_text="...".
    All controls are overridable, including those not passed to interface.
    """
    args = group.Group.with_overrides(kwargs)
    _, defs = workarounds.run_in_thread_if_in_async(module.app.run, defs={"args": args})
    if "result" not in defs:
        raise RuntimeError(
            f"moops.run() expected {module.__name__} to expose a variable named "
            "'result'"
        )
    return defs["result"]
