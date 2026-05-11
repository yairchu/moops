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
        self._write()
        self.select(name)

    def rename(self, old_name: str, new_name: str) -> None:
        if not old_name or not new_name:
            return
        args = self._data.get(old_name)
        if args is None:
            return
        if old_name != new_name:
            del self._data[old_name]
        self._data[new_name] = args
        self._write()
        self.select(new_name)

    def delete(self, name: str) -> None:
        if name not in self._data:
            return
        del self._data[name]
        self._write()
        if self.get_current() == name:
            self.select("")

    def _write(self) -> None:
        json.dump({"presets": self._data}, self._filename.open("w"), indent=2)
