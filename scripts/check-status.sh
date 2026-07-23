#!/usr/bin/env bash
set -euo pipefail

strict=0
receipt=".check-runs/latest.json"

usage() {
  echo "usage: scripts/check-status.sh [--strict] [--receipt path]" >&2
  exit 2
}

while (( $# > 0 )); do
  case "$1" in
    --strict)
      strict=1
      shift
      ;;
    --receipt)
      # Guard the operand: under `set -u` a bare `--receipt` reports a raw
      # "$2: unbound variable" from this line instead of this script's own usage error.
      (( $# >= 2 )) || usage
      receipt="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

cd "$(git rev-parse --show-toplevel)"

if [[ ! -f "$receipt" ]]; then
  echo "missing check receipt: $receipt" >&2
  exit 1
fi

hash_stream() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  else
    openssl dgst -sha256 | awk '{print $NF}'
  fi
}

hash_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 -- "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum -- "$1" | awk '{print $1}'
  else
    openssl dgst -sha256 "$1" | awk '{print $NF}'
  fi
}

worktree_fingerprint() {
  {
    printf 'HEAD %s\n' "$(git rev-parse HEAD)"
    printf 'STATUS\n'
    git status --porcelain=v1 --untracked-files=all \
      | sed '/^?? \.check-runs\//d;/^?? \.check-cache\//d'
    printf 'DIFF_CACHED\n'
    git diff --cached --binary
    printf 'DIFF_WORKTREE\n'
    git diff --binary
    printf 'UNTRACKED\n'
    while IFS= read -r file; do
      case "$file" in
        .check-runs/*|.check-cache/*) continue ;;
      esac
      [[ -f "$file" ]] || continue
      printf '%s\n' "$file"
      hash_file "$file"
    done < <(git ls-files --others --exclude-standard)
  } | hash_stream
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  else
    command -v python
  fi
}

toolchain_fingerprint() {
  {
    bash --version 2>&1 | head -n 1
    git --version 2>&1
    "$(python_bin)" --version 2>&1
    if command -v uv >/dev/null 2>&1; then
      uv --version 2>&1
    else
      echo "uv unavailable"
    fi
    if command -v uv >/dev/null 2>&1 && [ -f pyproject.toml ]; then
      project_python="$(uv python find 2>/dev/null || true)"
      if [ -n "$project_python" ]; then
        printf 'project-python: '
        "$project_python" --version 2>&1
      else
        echo "project-python unavailable"
      fi
    fi
    requested_node=""
    if [ -f .node-version ]; then
      requested_node="$(tr -d '[:space:]' < .node-version)"
    elif [ -f .nvmrc ]; then
      requested_node="$(tr -d '[:space:]' < .nvmrc)"
    fi
    if [ -n "$requested_node" ] && command -v fnm >/dev/null 2>&1; then
      printf 'node: '
      fnm exec --using="$requested_node" -- node --version 2>&1
      printf 'npm: '
      fnm exec --using="$requested_node" -- npm --version 2>&1
    elif command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
      printf 'node: '
      node --version 2>&1
      printf 'npm: '
      npm --version 2>&1
    else
      echo "node/npm unavailable"
    fi
  } | hash_stream
}

dependency_fingerprint() {
  while IFS= read -r dependency_file; do
    printf '%s\n' "$dependency_file"
    hash_file "$dependency_file"
  done < <(
    git ls-files -- \
      'uv.lock' 'pyproject.toml' 'requirements*.txt' \
      'package-lock.json' 'npm-shrinkwrap.json' 'pnpm-lock.yaml' 'yarn.lock' \
      | sort
  ) | hash_stream
}

current_head="$(git rev-parse HEAD)"
current_fingerprint="$(worktree_fingerprint)"
current_toolchain_fingerprint="$(toolchain_fingerprint)"
current_dependency_fingerprint="$(dependency_fingerprint)"
current_git_worktree="$(pwd -P)"
current_git_common_dir="$(cd "$(git rev-parse --git-common-dir)" && pwd -P)"

export CHECK_STATUS_RECEIPT="$receipt"
export CHECK_STATUS_STRICT="$strict"
export CHECK_STATUS_HEAD="$current_head"
export CHECK_STATUS_FINGERPRINT="$current_fingerprint"
export CHECK_STATUS_TOOLCHAIN_FINGERPRINT="$current_toolchain_fingerprint"
export CHECK_STATUS_DEPENDENCY_FINGERPRINT="$current_dependency_fingerprint"
export CHECK_STATUS_GIT_WORKTREE="$current_git_worktree"
export CHECK_STATUS_GIT_COMMON_DIR="$current_git_common_dir"

"$(python_bin)" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

receipt_path = Path(os.environ["CHECK_STATUS_RECEIPT"])
strict = os.environ["CHECK_STATUS_STRICT"] == "1"
current_head = os.environ["CHECK_STATUS_HEAD"]
current_fingerprint = os.environ["CHECK_STATUS_FINGERPRINT"]
current_toolchain_fingerprint = os.environ["CHECK_STATUS_TOOLCHAIN_FINGERPRINT"]
current_dependency_fingerprint = os.environ["CHECK_STATUS_DEPENDENCY_FINGERPRINT"]
current_git_worktree = os.environ["CHECK_STATUS_GIT_WORKTREE"]
current_git_common_dir = os.environ["CHECK_STATUS_GIT_COMMON_DIR"]

payload = json.loads(receipt_path.read_text(encoding="utf-8"))
errors: list[str] = []

required = {
    "schema_version",
    "ok",
    "exit_code",
    "command",
    "run_id",
    "log_path",
    "git_head",
    "worktree_fingerprint_before",
    "worktree_fingerprint",
    "started_at",
    "finished_at",
    "started_at_epoch",
    "finished_at_epoch",
    "cache_allowed",
    "authoritative",
    "profile",
    "resource",
    "wall_duration_seconds",
    "cpu_duration_seconds",
    "peak_rss_bytes",
    "worker_allocation",
    "stage_outcomes",
    "sibling_commits",
    "git_common_dir",
    "git_worktree",
    "toolchain_fingerprint",
    "dependency_fingerprint",
}
missing = sorted(required - payload.keys())
if missing:
    errors.append(f"missing required fields: {', '.join(missing)}")
unknown = sorted(payload.keys() - required)
if unknown:
    errors.append(f"unknown fields: {', '.join(unknown)}")


def is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_object(
    value: object, path: str, required_fields: set[str]
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return None
    nested_missing = sorted(required_fields - value.keys())
    for field in nested_missing:
        errors.append(f"{path}.{field} is required")
    nested_unknown = sorted(value.keys() - required_fields)
    if nested_unknown:
        errors.append(
            "unknown fields: " + ", ".join(f"{path}.{field}" for field in nested_unknown)
        )
    return value


worker = validate_object(
    payload.get("worker_allocation"),
    "worker_allocation",
    {"requested", "allocated", "budget", "cooperative"},
)
if worker is not None:
    if not isinstance(worker.get("requested"), str):
        errors.append("worker_allocation.requested must be a string")
    for field in ("allocated", "budget"):
        value = worker.get(field)
        if not is_integer(value) or value <= 0:
            errors.append(f"worker_allocation.{field} must be a positive integer")
    if not isinstance(worker.get("cooperative"), bool):
        errors.append("worker_allocation.cooperative must be a boolean")

stages = payload.get("stage_outcomes")
if not isinstance(stages, list):
    errors.append("stage_outcomes must be an array")
else:
    for index, value in enumerate(stages):
        path = f"stage_outcomes[{index}]"
        stage = validate_object(value, path, {"name", "status", "duration_seconds"})
        if stage is None:
            continue
        if not isinstance(stage.get("name"), str) or not stage.get("name"):
            errors.append(f"{path}.name must be a non-empty string")
        if stage.get("status") not in {"pass", "fail", "skipped"}:
            errors.append(f"{path}.status must be pass, fail, or skipped")
        duration = stage.get("duration_seconds")
        if not is_number(duration) or duration < 0:
            errors.append(f"{path}.duration_seconds must be a non-negative number")

siblings = payload.get("sibling_commits")
if not isinstance(siblings, list):
    errors.append("sibling_commits must be an array")
else:
    for index, value in enumerate(siblings):
        path = f"sibling_commits[{index}]"
        sibling = validate_object(value, path, {"name", "expected", "resolved"})
        if sibling is None:
            continue
        if not isinstance(sibling.get("name"), str) or not sibling.get("name"):
            errors.append(f"{path}.name must be a non-empty string")
        for field in ("expected", "resolved"):
            commit = sibling.get(field)
            if commit is not None and not isinstance(commit, str):
                errors.append(f"{path}.{field} must be a string or null")
        expected = sibling.get("expected")
        if isinstance(expected, str) and sibling.get("resolved") != expected:
            errors.append(f"sibling commit mismatch: {sibling.get('name', path)}")

resource = payload.get("resource")
if resource is not None:
    resource_fields = {
        "mode",
        "host_class",
        "workers",
        "static_lanes",
        "wait_ms",
        "taskpolicy_applied",
    }
    admission = validate_object(resource, "resource", resource_fields)
    if admission is not None:
        if admission.get("mode") not in {"desktop", "burst"}:
            errors.append("resource.mode must be desktop or burst")
        if admission.get("host_class") not in {"normal", "constrained", "burst"}:
            errors.append("resource.host_class must be normal, constrained, or burst")
        for field in ("workers", "static_lanes"):
            value = admission.get(field)
            if not is_integer(value) or value <= 0:
                errors.append(f"resource.{field} must be a positive integer")
        wait_ms = admission.get("wait_ms")
        if not is_integer(wait_ms) or wait_ms < 0:
            errors.append("resource.wait_ms must be a non-negative integer")
        if not isinstance(admission.get("taskpolicy_applied"), bool):
            errors.append("resource.taskpolicy_applied must be a boolean")

if payload.get("schema_version") != "check_receipt.v2":
    errors.append("schema_version must be check_receipt.v2")
if payload.get("exit_code") != 0:
    errors.append(f"exit code was {payload.get('exit_code')}, not 0")
if payload.get("ok") is not True:
    errors.append("receipt ok is not true")
if strict and (payload.get("profile") != "edit" or payload.get("authoritative") is not True):
    errors.append("strict status requires an authoritative edit receipt")
if payload.get("git_head") != current_head:
    errors.append("git head mismatch")
if payload.get("git_worktree") != current_git_worktree:
    errors.append("git worktree mismatch")
if payload.get("git_common_dir") != current_git_common_dir:
    errors.append("git common dir mismatch")
if payload.get("worktree_fingerprint") != current_fingerprint:
    errors.append("worktree fingerprint mismatch")
if payload.get("toolchain_fingerprint") != current_toolchain_fingerprint:
    errors.append("toolchain fingerprint mismatch")
if payload.get("dependency_fingerprint") != current_dependency_fingerprint:
    errors.append("dependency fingerprint mismatch")
if payload.get("finished_at_epoch", -1) < payload.get("started_at_epoch", 0):
    errors.append("finished_at is before started_at")
# check-runner.sh's only caller (check.sh) never mutates the tree (ruff format --check, gen/vendor
# --check, pytest) — before/after should be identical. A mismatch means either something else
# touched the tree mid-run, or the two fields were set inconsistently by hand.
fp_before = payload.get("worktree_fingerprint_before")
fp_after = payload.get("worktree_fingerprint")
if fp_before is not None and fp_before != fp_after:
    errors.append("worktree changed during the run (fingerprint_before != fingerprint_after)")

log_path = Path(payload.get("log_path", ""))
if not log_path.is_file():
    errors.append(f"log path missing: {log_path}")
else:
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    run_id = payload.get("run_id", "")
    exit_code = payload.get("exit_code")
    # Require the exact START/FINISH markers check-runner.sh itself writes (not tool output, which
    # varies by ruff/pyright/pytest version) — a receipt whose run_id merely appears somewhere in an
    # unrelated or hand-written log no longer passes; the log must actually bracket this run.
    started_marker = f"CHECK_RUN_STARTED run_id={run_id}"
    finished_marker = f"CHECK_RUN_FINISHED run_id={run_id} exit_code={exit_code}"
    if not run_id or started_marker not in log_text:
        errors.append("log is missing the CHECK_RUN_STARTED marker for this run_id")
    if not run_id or finished_marker not in log_text:
        errors.append("log is missing the CHECK_RUN_FINISHED marker for this run_id/exit_code")

# Cache freshness is gated by the runner-controlled cache_allowed flag, not by
# scanning command output for the substring "cache hit" (which false-positives
# on any tool that legitimately prints it).
if strict and payload.get("cache_allowed") is True:
    errors.append("cache-allowed run cannot satisfy strict status")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    raise SystemExit(1)

print("Verification: PASS")
print(f"Run id: {payload['run_id']}")
print(f"Git head: {payload['git_head']}")
print(f"Worktree fingerprint: {payload['worktree_fingerprint']}")
print(f"Receipt: {receipt_path}")
PY
