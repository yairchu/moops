import types
import typing

from . import group, workarounds
from .interface import Interface


class _App(typing.Protocol):
    def run(
        self, defs: dict[str, typing.Any]
    ) -> tuple[typing.Iterable[typing.Any], typing.Mapping[str, object]]: ...


def interface_of(
    module: types.ModuleType,
    *,
    args: group.Group | None = None,
    defs: dict[str, typing.Any] | None = None,
) -> Interface:
    """Return a notebook's Interface without running its computation.

    Notebooks can skip heavy work during interface queries::

        mo.stop(args.is_interface_query)

    Useful for surfacing a notebook's controls into a parent notebook without
    embedding it, e.g. when calling the notebook in a loop via ``moops.run()``.

    Pass a bound child ``args`` group to declare controls from a child notebook
    before the parent reaches a result-gated embed. This lets top-level CLI
    parsing and ``--help`` see child options such as ``--state-save-path`` even
    if the real embed only runs after the parent's computation. ``defs`` can
    override additional child definitions needed to reach the desired controls.
    """
    return interface_of_app(typing.cast(_App, module.app), args=args, defs=defs)


def interface_of_app(
    app: _App,
    *,
    args: group.Group | None = None,
    defs: dict[str, typing.Any] | None = None,
) -> Interface:
    args = group.Group.for_interface_query() if args is None else args
    query_args = typing.cast(typing.Any, args)
    was_interface_query = query_args._is_interface_query
    query_args._is_interface_query = True
    run_defs = {**(defs or {}), "args": args}
    try:
        _, result_defs = workarounds.run_in_thread_if_in_async(app.run, defs=run_defs)
    finally:
        query_args._is_interface_query = was_interface_query
    return typing.cast(Interface, result_defs["interface"])


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
