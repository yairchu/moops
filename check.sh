#!/bin/bash

set -ex

uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run vulture src/ tests/ examples/ --ignore-names "_,__generated_with"
uv run pytest -q
uv run marimo check examples
uv run pymarkdown --config .pymarkdown.json scan -r -e .pytest_cache -e .venv -e .claude .
