import sys
import pathlib

# notebook.py uses `import name_casing` (sibling import), so examples/ must be on the path.
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "examples"))
