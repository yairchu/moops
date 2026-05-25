import asyncio
import typing

import marimo as mo

from . import _options, interface, workarounds


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
    marimo cell that chooses the app clone and argument subgroup. Pass the
    returned subgroup explicitly to the async embed cell with
    ``defs={"args": embed_args}``. The third return value contains branch
    interfaces, so CLI help and validation can run before embedding.
    """

    apps = _apps_from_selector(selector)
    selected_key = getattr(selector, "_selected_key", selector.value)
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
    branch_keys = (selected_key, *(key for key in variants if key != selected_key))
    branch_interfaces = tuple(
        _interface_of_app(apps[key], variants[key])
        for key in branch_keys
        if key in apps
    )
    return app.clone(), args, branch_interfaces


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

    async def embed(self, defs: dict[str, typing.Any]) -> "Passthrough":
        unexpected = defs.keys() - {"args"}
        if unexpected:
            raise ValueError(
                f"moops.Passthrough received unexpected defs keys: {unexpected}"
            )
        return self


def _embed_in_script(app: _App, defs: dict[str, typing.Any]) -> typing.Any:
    _, computed_defs = app.run(defs=defs)
    result = Passthrough(dict(computed_defs))
    if "interface" in computed_defs:
        result.defs["interface"] = computed_defs["interface"]
    return result
