import json
import pathlib
import typing


class Presets:
    """Preset selector backed by a JSON file."""

    def __init__(
        self,
        filename: str | pathlib.Path,
        get_selected_preset: typing.Callable[[], str | None],
        set_selected_preset: typing.Callable[[str | None], None],
    ) -> None:
        self._filename = pathlib.Path(filename)
        self.get_current = get_selected_preset
        self.select = set_selected_preset
        self._data: dict[str, str] = (
            json.load(self._filename.open()).get("presets", {})
            if self._filename.exists()
            else {}
        )

    def list(self) -> typing.Iterable[str]:
        return self._data.keys()

    @property
    def selected_args(self) -> str:
        key = self.get_current()
        return self.args_for(key) if key else ""

    @property
    def default_args(self) -> str:
        return self.args_for("default")

    def args_for(self, name: str | None) -> str:
        return self._data.get(name, "") if name else ""

    def save(self, name: str, args: str) -> None:
        if not name:
            return
        self._data[name] = args
        json.dump({"presets": self._data}, self._filename.open("w"), indent=2)
        self.select(name)
