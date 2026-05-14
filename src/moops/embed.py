import typing


class _Embed(typing.Protocol):
    defs: typing.Mapping[str, typing.Any]


class Passthrough:
    """
    Override an inner embed with the results of an existing embed.
    """

    def __init__(self, embed: _Embed) -> None:
        self.defs = {"result": embed.defs["result"], "interface": None}
        self.output = None

    async def embed(self, defs: dict[str, typing.Any]) -> "Passthrough":
        unexpected = defs.keys() - {"args"}
        if unexpected:
            raise ValueError(
                f"moops.embed.Passthrough received unexpected defs keys: {unexpected}"
            )
        return self
