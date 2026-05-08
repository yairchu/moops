import pathlib

from moops.interface import Interface
from moops.presets import Presets


def test_preset_ui_elements_stable_across_renders(tmp_path: pathlib.Path) -> None:
    presets = Presets(tmp_path / "presets.json")
    iface = Interface(controls=(), presets=presets, command="script.py")  # type: ignore[arg-type]
    iface._mime_()  # type: ignore[misc]
    first = iface._name_input  # type: ignore[attr-defined]
    iface._mime_()  # type: ignore[misc]
    assert iface._name_input is first  # type: ignore[attr-defined]
