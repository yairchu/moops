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


class App:
    """
    Wrap a marimo app with lean script-mode embeds.

    In script mode, only the embedded notebook's ``result`` definition is
    retained, so intermediate definitions and rendered outputs can be released
    after the embed completes.

    This also works around marimo nested embed failures in script mode,
    see https://github.com/marimo-team/marimo/issues/9572
    """

    def __init__(self, app: _App) -> None:
        self._app = app

    def clone(self) -> "App":
        return App(self._app.clone())

    async def embed(self, defs: dict[str, typing.Any] | None = None) -> typing.Any:
        if mo.running_in_notebook():
            return await self._app.embed(defs=defs)
        return await asyncio.to_thread(_embed_in_script, self._app, defs or {})


class Passthrough:
    """
    Override an inner embed with the results of an existing embed.
    """

    def __init__(self, source: _Embed | dict[str, typing.Any]) -> None:
        self.defs = {
            "result": (source if isinstance(source, dict) else source.defs)["result"],
            "interface": interface.Interface(
                controls=typing.cast(tuple[typing.Any], ())
            ),
        }
        self.output = None

    async def embed(self, defs: dict[str, typing.Any]) -> "Passthrough":
        unexpected = defs.keys() - {"args"}
        if unexpected:
            raise ValueError(
                f"moops.embed.Passthrough received unexpected defs keys: {unexpected}"
            )
        return self


def _embed_in_script(app: _App, defs: dict[str, typing.Any]) -> typing.Any:
    _, computed_defs = app.run(defs=defs)
    return Passthrough(dict(computed_defs))
