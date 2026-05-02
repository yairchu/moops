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


def defaults(module: types.ModuleType) -> dict[str, str | None]:
    """Return the default value for each str control in the notebook."""
    result: dict[str, str | None] = {}
    seen: set[str] = set()
    for meta in _discover(module).values():
        cli = meta.cli
        if meta.overridden or isinstance(cli, _options.FlagControl):
            continue
        key = cli.opt.label.lower().replace(" ", "_")
        if key not in seen:
            seen.add(key)
            info = cli.cli_info()
            assert isinstance(info, _options.OptionDesc)
            result[key] = info.default
    return result


def _strategies_from_meta(
    control_meta: dict[int, _options.ControlMeta],
) -> st.SearchStrategy[dict[str, typing.Any]]:
    kwarg_strategies: dict[str, st.SearchStrategy] = {}
    seen: set[str] = set()

    for meta in control_meta.values():
        cli = meta.cli
        if meta.overridden:
            continue
        key = cli.opt.label.lower().replace(" ", "_")
        if key in seen:
            continue
        seen.add(key)

        if isinstance(cli, _options.FlagControl):
            kwarg_strategies[key] = st.booleans()
        else:
            info = cli.cli_info()
            assert isinstance(info, _options.OptionDesc)
            if info.allowed_values is not None:
                base: st.SearchStrategy = st.sampled_from(info.allowed_values)
                is_nullable_dropdown = (
                    isinstance(cli, _options.DropdownControl) and cli.has_no_flag
                )
                if is_nullable_dropdown:
                    base = st.one_of(st.none(), base)
            else:
                # TODO: add range-aware strategy for number controls
                base = st.text().filter(lambda v: not v.startswith("-"))
            kwarg_strategies[key] = st.one_of(st.none(), base)

    return st.fixed_dictionaries(kwarg_strategies).map(
        lambda d: {k: v for k, v in d.items() if v is not None}
    )
