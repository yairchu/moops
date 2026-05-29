import pathlib
import sys

# Notebooks use sibling imports (e.g. composition/notebook.py does
# `import name_casing`), which resolve to whichever folder the notebook lives
# in. Put examples/ and each of its subfolders on the path so those imports
# work when the notebooks are imported during tests.
_examples = pathlib.Path(__file__).parent.parent / "examples"
_subdirs = sorted(
    p for p in _examples.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))
)
for _path in [_examples, *_subdirs]:
    sys.path.insert(0, str(_path))
