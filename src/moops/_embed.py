import asyncio
import typing

import marimo as mo

from . import interface


class _Embed(typing.Protocol):
    defs: typing.Mapping[str, typing.Any]


class _App(typing.Protocol):
    def clone(self) -> "_App": ...

    async def embed(self, defs: dict[str, typing.Any] | None = None) -> typing.Any: ...

    def run(
        self, defs: dict[str, typing.Any]
    ) -> tuple[typing.Iterable[typing.Any], typing.Mapping[str, object]]: ...


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
        return await app.embed(defs=defs)
    return await asyncio.to_thread(_embed_in_script, app, defs or {})


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
