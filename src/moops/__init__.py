from importlib.metadata import version

from . import workarounds
from ._embed import Passthrough, embed
from ._run import interface_of, run
from ._run_button import run_button
from .group import Group
from .interface import Interface
from .presets import Presets

__version__ = version("moops")

__all__ = [
    "Group",
    "Interface",
    "Passthrough",
    "Presets",
    "__version__",
    "embed",
    "interface_of",
    "run",
    "run_button",
    "workarounds",
]
