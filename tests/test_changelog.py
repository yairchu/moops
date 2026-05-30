import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_unreleased_added_symbols_do_not_reappear_as_changed_or_fixed() -> None:
    sections = _unreleased_subsections()
    added_symbols = _backtick_symbols(sections.get("Added", ""))
    repeated = {
        section: sorted(added_symbols & _backtick_symbols(text))
        for section, text in sections.items()
        if section in {"Changed", "Fixed"}
    }

    assert not any(repeated.values()), (
        "Symbols listed under Unreleased > Added should not also be listed as "
        f"changed or fixed in the same release: {repeated}"
    )


def _unreleased_subsections() -> dict[str, str]:
    changelog = (ROOT / "CHANGELOG.md").read_text()
    [_, rest] = changelog.split("## [Unreleased]", 1)
    unreleased = rest.split("\n## ", 1)[0]
    matches = list(re.finditer(r"^### (?P<title>.+)$", unreleased, re.MULTILINE))
    return {
        match.group("title"): unreleased[
            match.end() : matches[i + 1].start() if i + 1 < len(matches) else None
        ]
        for i, match in enumerate(matches)
    }


def _backtick_symbols(text: str) -> set[str]:
    return set(re.findall(r"`([^`]+)`", text))
