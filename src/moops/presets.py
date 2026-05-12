import inspect
import json
import pathlib
import typing


class Presets:
    """Preset selector backed by a JSON file."""

    def __init__(
        self,
        get_selected_preset: typing.Callable[[], str | None],
        set_selected_preset: typing.Callable[[str | None], None],
        *,
        filename: str | pathlib.Path | None = None,
    ) -> None:
        self._filename = (
            pathlib.Path(filename) if filename is not None else _infer_filename()
        )
        self.get_current = get_selected_preset
        self.select = set_selected_preset
        if self._filename.exists():
            with self._filename.open() as f:
                self._data: dict[str, str] = json.load(f).get("presets", {})
        else:
            self._data = {}

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
        self.save(new_name, args)

    def delete(self, name: str) -> None:
        if name not in self._data:
            return
        del self._data[name]
        self._write()
        current = self.get_current()
        self.select("" if current in (None, name) else current)

    def _write(self) -> None:
        with self._filename.open("w") as f:
            json.dump({"presets": self._data}, f, indent=2)


def _infer_filename() -> pathlib.Path:
    caller = _marimo_notebook_filename() or _stack_filename()
    return caller.with_name(f"{caller.stem}_presets.json")


def _marimo_notebook_filename() -> pathlib.Path | None:
    try:
        from marimo._runtime.context import ContextNotInitializedError, get_context
    except ImportError:
        return None

    try:
        filename = get_context().filename
    except ContextNotInitializedError:
        return None
    if filename is None:
        return None

    path = pathlib.Path(filename)
    return None if path.name.startswith("<") else path


def _stack_filename() -> pathlib.Path:
    caller = pathlib.Path(inspect.stack()[2].filename)
    if caller.name.startswith("<"):
        raise ValueError("Presets filename could not be inferred; pass a filename")
    return caller
