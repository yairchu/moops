import importlib
import pathlib
import re
import typing

ROOT = pathlib.Path(__file__).parents[1]


def test_moops_references_resolve() -> None:
    """Catch stale dotted moops API references in docs, comments, and strings."""
    regexp = re.compile(r"(?<![\w/-])moops(?:\.[A-Za-z_]\w*)+")
    stale_references: list[str] = []
    for path in _reference_files():
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            for match in regexp.finditer(line):
                reference = match.group(0)
                try:
                    _resolve_reference(reference)
                except AttributeError:
                    stale_references.append(
                        f"{path.relative_to(ROOT)}:{lineno}: {reference}"
                    )

    assert not stale_references


def _reference_files() -> typing.Iterator[pathlib.Path]:
    yield ROOT / "README.md"
    for directory in ["src", "tests", "examples"]:
        yield from (ROOT / directory).rglob("*.py")


def _resolve_reference(reference: str) -> None:
    [head, *tail] = reference.split(".")
    assert head == "moops"
    obj: typing.Any = importlib.import_module(head)
    for i, part in enumerate(tail):
        try:
            obj = importlib.import_module(".".join([head, *tail[: i + 1]]))
        except ModuleNotFoundError:
            pass
        else:
            continue
        obj = getattr(obj, part)
