#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$(dirname "$0")/.."

uv run ruff check bambu tools tests
uv run ruff format --check bambu tools tests
uv run python -m unittest discover -s tests
