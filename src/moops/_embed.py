import asyncio
import typing

import marimo as mo

from . import _options, _variant, interface
from ._run import interface_of_app


class _Embed(typing.Protocol):
    defs: typing.Mapping[str, typing.Any]


class _App(typing.Protocol):
    def clone(self) -> "_App": ...

    async def embed(self, defs: dict[str, typing.Any] | None = None) -> typing.Any: ...

    def run(
        self, defs: dict[str, typing.Any]
    ) -> tuple[typing.Iterable[typing.Any], typing.Mapping[str, object]]: ...


def variant_embed(
    group: typing.Any,
    selector: typing.Any,
    *,
    prefix: str,
) -> tuple[_App, typing.Any, tuple[interface.Interface, ...]]:
    """Prepare the currently selected notebook app for embedding.

    This function intentionally performs only sync work so it can live in the
    marimo cell that chooses the app clone and argument subgroup.

    Returns ``(selected_app, embed_args, inactive_interfaces)``:

    * ``selected_app`` is a clone of the selected app, for passing to
      ``moops.embed()``.
    * ``embed_args`` is the selected variant subgroup, for passing as
      ``defs={"args": embed_args}``.
    * ``inactive_interfaces`` contains inspected interfaces for unselected
      branches, so CLI help and validation can include inactive branch options
      before embedding.

    The tuple return is deliberate: marimo's embed dependency tracking expects
    app clones to be bound directly to cell variables. Unpacking the tuple into
    ``selected_app`` and ``embed_args`` keeps embedded notebook widgets
    responsive to interactive changes.
    """

    apps = _apps_from_selector(selector)
    selected_key = _variant.selected_key(selector)
    try:
        app = apps[selected_key]
    except KeyError as exc:
        raise KeyError(
            f"selected embed variant {selected_key!r} has no matching app"
        ) from exc
    variants = group.variant(prefix, selector)
    try:
        args = variants[selected_key]
    except KeyError as exc:
        raise KeyError(
            f"selected embed variant {selected_key!r} has no matching group"
        ) from exc
    inactive_interfaces = tuple(
        interface_of_app(apps[k], args=v)
        for k, v in variants.items()
        if k != selected_key
    )
    if not mo.running_in_notebook() and any(
        iface.has_prefixed_options(group._state) for iface in inactive_interfaces
    ):
        group._state.failed_validation = True
    return app.clone(), args, inactive_interfaces


def _apps_from_selector(selector: typing.Any) -> typing.Mapping[typing.Any, _App]:
    input_control = getattr(selector, "_moops_input", None)
    if not isinstance(input_control, _options.DropdownControl):
        raise TypeError("variant_embed apps can only be inferred from a moops dropdown")
    return typing.cast(typing.Mapping[typing.Any, _App], input_control.dropdown_opts)


async def embed(
    app: _App,
    defs: dict[str, typing.Any] | None = None,
    *,
    keep: typing.Sequence[str] = (),
) -> typing.Any:
    """
    Embed a marimo app, with lean script-mode embeds.

    In script mode, only the embedded notebook's ``result`` definition is
    retained, so intermediate definitions can be released after the embed
    completes. Pass additional definition names in ``keep`` to retain them as
    well (in notebook mode all definitions are exposed and ``keep`` has no
    effect). The embedded notebook's rendered cell outputs are stacked on the
    returned object's ``output``, matching notebook-mode embeds.

    When ``args`` is the only overridden definition, the embedded notebook's
    interface also shows a CLI command that reproduces the embed's current
    setup standalone.

    This also works around marimo nested embed failures in script mode,
    see https://github.com/marimo-team/marimo/issues/9572
    """
    keep = _normalize_keep(keep)
    _record_extra_overrides(defs)
    if mo.running_in_notebook():
        _raise_if_same_cell_app(app)
        return await app.embed(defs=defs)
    return await asyncio.to_thread(_embed_in_script, app, defs or {}, keep)


def _record_extra_overrides(defs: dict[str, typing.Any] | None) -> None:
    """Stamp on the injected args Group which other defs were overridden.

    The embedded notebook's interface offers a CLI command reproducing the
    current setup only when ``args`` is the only override: defs injected
    directly (e.g. a dataframe) cannot be reproduced from the command line.
    The interface cannot detect overrides itself — marimo merges them into
    the run's globals without a trace — so embed() records them here.
    """
    args = (defs or {}).get("args")
    if args is not None and hasattr(args, "_embedded_extra_overrides"):
        args._embedded_extra_overrides = frozenset(defs or ()) - {"args"}


def _normalize_keep(keep: typing.Sequence[str]) -> tuple[str, ...]:
    if isinstance(keep, str):
        raise TypeError("keep must be a sequence of definition names, not a string")
    return tuple(keep)


def _raise_if_same_cell_app(app: _App) -> None:
    """Mirror marimo's same-cell embed guard for the moops wrapper."""
    from marimo._runtime.context import get_context

    ctx = get_context()
    execution_context = ctx.execution_context
    if execution_context is None:
        return
    cell_id = execution_context.cell_id
    for var, value in ctx.globals.items():
        if (
            value is app or getattr(value, "app", None) is app
        ) and cell_id in ctx.graph.get_defining_cells(var):
            raise RuntimeError(
                "App.embed() cannot be called in the cell that "
                "imports the app. Call embed() in another cell."
            )


class Passthrough:
    """
    Override an inner embed with the results of an existing embed.
    """

    def __init__(
        self,
        source: _Embed | dict[str, typing.Any],
        *,
        keep: typing.Sequence[str] = (),
    ) -> None:
        keep = _normalize_keep(keep)
        source_defs = source if isinstance(source, dict) else source.defs
        self.defs: dict[str, typing.Any] = {
            "interface": interface.Interface(controls=()),
        }
        for name in ("result", *keep):
            if name in source_defs:
                self.defs[name] = source_defs[name]
        self.output: mo.Html | None = None

    def _forwarded(self) -> dict[str, typing.Any]:
        return {k: v for k, v in self.defs.items() if k != "interface"}

    def __eq__(self, other: object) -> bool:
        # Passthroughs are interchangeable when they forward the same defs.
        # marimo's embed-output cache compares the `defs` it was handed (see
        # marimo's `_defs_equal`): when a Passthrough is passed as an
        # `input_instance` override and the embedding cell re-runs, a freshly
        # built Passthrough must still compare equal, or the cache always
        # misses and the embedded notebook's UI (e.g. dropdowns) resets on
        # every interaction. Compare the forwarded defs by identity to stay
        # cheap and to avoid ambiguous element-wise `__eq__` on array results.
        if not isinstance(other, Passthrough):
            return NotImplemented
        mine, theirs = self._forwarded(), other._forwarded()
        return mine.keys() == theirs.keys() and all(mine[k] is theirs[k] for k in mine)

    def __hash__(self) -> int:
        return hash(frozenset((k, id(v)) for k, v in self._forwarded().items()))

    def clone(self) -> "Passthrough":
        # A Passthrough just forwards a fixed result, so cloning is a no-op:
        # passthroughs forwarding the same result are interchangeable (see
        # __eq__). Implemented to satisfy the _App protocol.
        return self

    async def embed(self, defs: dict[str, typing.Any] | None = None) -> "Passthrough":
        self._check(defs or {})
        return self

    def run(
        self, defs: dict[str, typing.Any]
    ) -> tuple[typing.Iterable[typing.Any], dict[str, typing.Any]]:
        self._check(defs)
        # Hand back a copy so callers can't mutate our forwarded defs.
        return (), dict(self.defs)

    @staticmethod
    def _check(defs: dict[str, typing.Any]) -> None:
        unexpected = defs.keys() - {"args"}
        if unexpected:
            raise ValueError(
                f"moops.Passthrough received unexpected defs keys: {unexpected}"
            )


def _embed_in_script(
    app: _App,
    defs: dict[str, typing.Any],
    keep: tuple[str, ...] = (),
) -> typing.Any:
    output, computed_defs = app.run(defs=defs)
    result = Passthrough(dict(computed_defs), keep=keep)
    if "interface" in computed_defs:
        result.defs["interface"] = computed_defs["interface"]
    result.output = mo.vstack([x for x in output if x is not None])
    return result
