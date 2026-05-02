import contextlib
import types
import typing

from hypothesis import strategies as st

from . import _options, group


def _discover(module: types.ModuleType) -> dict[int, _options.ControlMeta]:
    args = group.Group.with_overrides({})
    module.app.run(defs={"args": args})
    return args._state.control_meta  # type: ignore


def from_notebook(module: types.ModuleType) -> st.SearchStrategy[dict[str, typing.Any]]:
    "Return a hypothesis strategy that generates valid kwargs for moops.run(module)."
    return _strategies_from_meta(_discover(module))


def defaults(module: types.ModuleType) -> dict[str, typing.Any]:
    """Return the default value for each control, nested by subgroup prefix."""
    result: dict[str, typing.Any] = {}
    for meta in _discover(module).values():
        if meta.overridden:
            continue
        key = meta.cli.opt.label.lower().replace(" ", "_")
        prefix = meta.option_prefix.rstrip("-")
        target = result.setdefault(prefix, {}) if prefix else result
        assert key not in target, f"Duplicate control key: {key!r}"
        if hasattr(meta.cli, "default"):
            target[key] = meta.cli.default # type: ignore
    return result


def _strategies_from_meta(
    control_meta: dict[int, _options.ControlMeta],
) -> st.SearchStrategy[dict[str, typing.Any]]:
    kwarg_strategies: dict[str, st.SearchStrategy] = {}

    for meta in control_meta.values():
        if meta.overridden:
            continue
        key = meta.cli.opt.label.lower().replace(" ", "_")
        assert key not in kwarg_strategies, f"Duplicate control key: {key!r}"
        kwarg_strategies[key] = meta.cli.strategy()

    return st.fixed_dictionaries(kwarg_strategies).map(
        lambda d: {k: v for k, v in d.items() if v is not None}
    )
