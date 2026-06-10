import dataclasses
import inspect
import json
import pathlib
import typing


@dataclasses.dataclass(frozen=True)
class PendingCliInput:
    """A command-box submission awaiting display in the script callout.

    Stored alongside the selected preset so a failed (or in-flight) submission
    survives the marimo rerun that renders its error message.
    """

    text: str
    errors: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class _UIState:
    """Value stored in the user-provided preset-selection ``mo.state``.

    A single state drives the whole root callout: it carries both the selected
    preset name and any pending command-box input.
    """

    preset: str | None = None
    pending_cli: PendingCliInput | None = None


def _as_ui_state(raw: typing.Any) -> _UIState:
    if isinstance(raw, _UIState):
        return raw
    # The initial mo.state value (None) or a legacy bare preset name.
    return _UIState(preset=raw)


class Presets:
    """Preset selector backed by a JSON file."""

    def __init__(
        self,
        get_selected_preset: typing.Callable[[], typing.Any],
        set_selected_preset: typing.Callable[[typing.Any], None],
        *,
        filename: str | pathlib.Path | None = None,
    ) -> None:
        self._filename = (
            pathlib.Path(filename) if filename is not None else _infer_filename()
        )
        self._get_raw = get_selected_preset
        self._set_raw = set_selected_preset
        if self._filename.exists():
            with self._filename.open() as f:
                self._data: dict[str, str] = json.load(f).get("presets", {})
        else:
            self._data = {}

    def get_current(self) -> str | None:
        return _as_ui_state(self._get_raw()).preset

    def select(self, name: str | None) -> None:
        """Select a preset, clearing any pending command-box input."""
        self._set_raw(_UIState(preset=name))

    def get_pending_cli(self) -> PendingCliInput | None:
        return _as_ui_state(self._get_raw()).pending_cli

    def set_pending_cli(self, pending: PendingCliInput | None) -> None:
        current = _as_ui_state(self._get_raw())
        self._set_raw(dataclasses.replace(current, pending_cli=pending))

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
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None or frame.f_back.f_back is None:
        raise RuntimeError("Could not inspect caller frame")
    try:
        caller = pathlib.Path(frame.f_back.f_back.f_code.co_filename)
    finally:
        del frame
    if caller.name.startswith("<"):
        raise ValueError("Presets filename could not be inferred; pass a filename")
    return caller
