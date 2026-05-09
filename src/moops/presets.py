import json
import pathlib

import marimo as mo


class Presets(mo.ui.dropdown):
    """Preset selector backed by a JSON file. Subclass of mo.ui.dropdown so it
    drives marimo reactivity: cells that reference a Presets re-run when the
    selection changes."""

    def __init__(self, filename: str | pathlib.Path) -> None:
        self._filename = pathlib.Path(filename)
        self._data: dict[str, str] = {}
        if self._filename.exists():
            self._data = json.load(self._filename.open()).get("presets", {})
        super().__init__(
            options=list(self._data),
            value=None,
            label="Preset",
            allow_select_none=True,
        )

    @property
    def selected_args(self) -> str | None:
        return self._data.get(self.value) if self.value else None

    def save(self, name: str, args: str) -> None:
        if not name:
            return
        self._data[name] = args
        self._filename.write_text(json.dumps({"presets": self._data}, indent=2))
