import dataclasses
import json
import pathlib
import typing


@dataclasses.dataclass
class Presets:
    _filename: pathlib.Path

    def __init__(self, filename: str | pathlib.Path) -> None:
        self._filename = pathlib.Path(filename)

    def save(self, name: str, args: str) -> None:
        if not name:
            return
        path = self._filename
        existing: dict[str, typing.Any] = {}
        if path.exists():
            existing = json.loads(path.read_text()).get("presets", {})
        path.write_text(json.dumps({"presets": {**existing, name: args}}, indent=2))
