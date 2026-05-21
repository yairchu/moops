import concurrent.futures
import types
import typing

from . import group


def run(module: types.ModuleType, **kwargs: typing.Any) -> typing.Any:
    """Run a notebook as a function, returning its `result` variable.

    Keyword arguments override control values by option name
    (leading dashes removed and dashes replaced with underscores). For example,
    a text area with option "--input-text" is overridden with input_text="...".
    All controls are overridable, including those not passed to interface.
    """
    args = group.Group.with_overrides(kwargs)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        _, defs = executor.submit(module.app.run, defs={"args": args}).result()
    if "result" not in defs:
        raise RuntimeError(
            f"moops.run() expected {module.__name__} to expose a variable named "
            "'result'"
        )
    return defs["result"]
