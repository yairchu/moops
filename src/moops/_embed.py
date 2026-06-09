import asyncio
import typing

import marimo as mo

from . import _options, _variant, interface, workarounds


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
        _interface_of_app(apps[k], v) for k, v in variants.items() if k != selected_key
    )
    if not mo.running_in_notebook() and any(
        iface.has_prefixed_options(group._state) for iface in inactive_interfaces
    ):
        group._state.failed_validation = True
    return app.clone(), args, inactive_interfaces


def _interface_of_app(app: _App, args: typing.Any) -> interface.Interface:
    was_interface_query = args._is_interface_query
    args._is_interface_query = True
    try:
        _, defs = workarounds.run_in_thread_if_in_async(app.run, defs={"args": args})
    finally:
        args._is_interface_query = was_interface_query
    return typing.cast(interface.Interface, defs["interface"])


def _apps_from_selector(selector: typing.Any) -> typing.Mapping[typing.Any, _App]:
    input_control = getattr(selector, "_moops_input", None)
    if not isinstance(input_control, _options.DropdownControl):
        raise TypeError("variant_embed apps can only be inferred from a moops dropdown")
    return typing.cast(typing.Mapping[typing.Any, _App], input_control.dropdown_opts)


async def embed(app: _App, defs: dict[str, typing.Any] | None = None) -> typing.Any:
    """
    Embed a marimo app, with lean script-mode embeds.

    In script mode, only the embedded notebook's ``result`` definition is
    retained, so intermediate definitions and rendered outputs can be released
    after the embed completes.

    This also works around marimo nested embed failures in script mode,
    see https://github.com/marimo-team/marimo/issues/9572
    """
    if mo.running_in_notebook():
        _raise_if_same_cell_app(app)
        return await app.embed(defs=defs)
    return await asyncio.to_thread(_embed_in_script, app, defs or {})


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

    def __init__(self, source: _Embed | dict[str, typing.Any]) -> None:
        source_defs = source if isinstance(source, dict) else source.defs
        self.defs: dict[str, typing.Any] = {
            "interface": interface.Interface(
                controls=typing.cast(tuple[typing.Any], ())
            ),
        }
        if "result" in source_defs:
            self.defs["result"] = source_defs["result"]
        self.output = None

    def __eq__(self, other: object) -> bool:
        # Passthroughs are interchangeable when they forward the same result.
        # marimo's embed-output cache compares the `defs` it was handed (see
        # marimo's `_defs_equal`): when a Passthrough is passed as an
        # `input_instance` override and the embedding cell re-runs, a freshly
        # built Passthrough must still compare equal, or the cache always
        # misses and the embedded notebook's UI (e.g. dropdowns) resets on
        # every interaction. Compare the forwarded result by identity to stay
        # cheap and to avoid ambiguous element-wise `__eq__` on array results.
        if not isinstance(other, Passthrough):
            return NotImplemented
        if ("result" in self.defs) != ("result" in other.defs):
            return False
        return self.defs.get("result") is other.defs.get("result")

    def __hash__(self) -> int:
        return hash(id(self.defs.get("result")))

    async def embed(self, defs: dict[str, typing.Any]) -> "Passthrough":
        self._check(defs)
        return self

    def run(
        self, defs: dict[str, typing.Any]
    ) -> tuple[typing.Iterable[typing.Any], dict[str, typing.Any]]:
        self._check(defs)
        return (), self.defs

    @staticmethod
    def _check(defs: dict[str, typing.Any]) -> None:
        unexpected = defs.keys() - {"args"}
        if unexpected:
            raise ValueError(
                f"moops.Passthrough received unexpected defs keys: {unexpected}"
            )


def _embed_in_script(app: _App, defs: dict[str, typing.Any]) -> typing.Any:
    _, computed_defs = app.run(defs=defs)
    result = Passthrough(dict(computed_defs))
    if "interface" in computed_defs:
        result.defs["interface"] = computed_defs["interface"]
    return result
