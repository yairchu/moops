#!/bin/bash

set -ex

uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run vulture src/ tests/
uv run pytest -q
