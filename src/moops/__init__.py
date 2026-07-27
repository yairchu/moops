from importlib.metadata import version

from . import ui, workarounds
from ._embed import Passthrough, embed, variant_embed
from ._run import interface_of, run
from ._run_button import run_button
from .group import Group, OutputMode
from .interface import Interface
from .presets import Presets

__version__ = version("moops")

__all__ = [
    "Group",
    "Interface",
    "OutputMode",
    "Passthrough",
    "Presets",
    "__version__",
    "embed",
    "interface_of",
    "run",
    "run_button",
    "ui",
    "variant_embed",
    "workarounds",
]
