#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${CHECK_RESOURCE_ACTIVE:-0}" != "1" && "${CHECK_RESOURCE_MODE:-desktop}" != "off" && -z "${CI:-}" ]]; then
  exec python3 "$script_dir/check-resource.py" -- "$script_dir/check.sh" "$@"
fi

cd "$(dirname "$0")/.."

uv run ruff check bambu tools tests
uv run ruff format --check bambu tools tests
uv run python -m unittest discover -s tests
