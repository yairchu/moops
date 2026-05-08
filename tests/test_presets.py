import pathlib

from moops.interface import Interface
from moops.presets import Presets


def test_preset_ui_elements_stable_across_renders(tmp_path: pathlib.Path) -> None:
    presets = Presets(tmp_path / "presets.json")
    iface = Interface(controls=(), presets=presets, command="script.py")  # type: ignore[arg-type]
    assert iface._presets_ui is not None  # type: ignore[reportPrivateUsage]
    iface._mime_()  # type: ignore[misc]
    first = iface._presets_ui  # type: ignore[reportPrivateUsage]
    iface._mime_()  # type: ignore[misc]
    assert iface._presets_ui is first  # type: ignore[reportPrivateUsage]
