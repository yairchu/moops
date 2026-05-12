from importlib.metadata import version

from ._run import run
from .group import Group
from .interface import Interface
from .presets import Presets

__version__ = version("moops")

__all__ = ["Group", "Interface", "Presets", "__version__", "run"]
