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


def run(
    module: types.ModuleType,
    *,
    output_mode: group.OutputMode | None = group.OutputMode.STDOUT,
    **kwargs: typing.Any,
) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable.

    Keyword arguments override control values by option name
    (leading dashes removed and dashes replaced with underscores). For example,
    a text area with option "--input-text" is overridden with input_text="...".
    All controls are overridable, including those not passed to interface.

    `output_mode` controls where the child's dual-output (``args.md``,
    ``args.figure``) goes. It defaults to ``OutputMode.STDOUT`` so a child run
    prints as it would on its own CLI; pass ``None`` to silence it, e.g. when
    looping and only the final iteration should be displayed. ``NOTEBOOK``
    builds marimo display objects, but ``run`` returns only ``result``, so they
    are not surfaced.
    """
    args = group.Group.with_overrides(kwargs)
    args.output_mode = output_mode
    _, defs = workarounds.run_in_thread_if_in_async(module.app.run, defs={"args": args})
    if "result" not in defs:
        raise RuntimeError(
            f"moops.run() expected {module.__name__} to expose a variable named "
            "'result'"
        )
    return defs["result"]
