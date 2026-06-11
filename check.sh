#!/bin/bash

set -ex

case "${1:-}" in
  "")
    ;;
  "--docs-only")
    uv run pymarkdown --config .pymarkdown.json scan -r -e .pytest_cache -e .venv -e .claude .
    uv run pytest -q tests/test_public_references.py tests/test_changelog.py
    echo "Docs checks successful!"
    exit 0
    ;;
  "-h" | "--help")
    echo "Usage: bash check.sh [--docs-only]"
    exit 0
    ;;
  *)
    echo "Usage: bash check.sh [--docs-only]" >&2
    exit 2
    ;;
esac

uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run vulture src/ tests/ examples/ --ignore-names "_,__generated_with,_clone,_convert_value,_label_html"
# symilar (from pylint) detects copy-paste duplication. It always exits 0, so
# we fail the build ourselves when it reports any duplicate runs.
dup_output=$(uv run symilar --duplicates=5 --ignore-comments --ignore-docstrings --ignore-signatures src/moops/*.py)
echo "$dup_output"
echo "$dup_output" | grep -q "duplicates=0" || { echo "Duplicate code detected (see above)"; exit 1; }
uv run marimo check examples
uv run pymarkdown --config .pymarkdown.json scan -r -e .pytest_cache -e .venv -e .claude .
uv run pytest -q
echo "All checks successful! See AGENTS.md for contribution guidelines not covered by these checks."
