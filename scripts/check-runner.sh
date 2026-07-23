#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 )); then
  echo "usage: scripts/check-runner.sh <command> [args...]" >&2
  exit 2
fi

cd "$(git rev-parse --show-toplevel)"

profile="${CHECK_PROFILE:-edit}"
case "$profile" in
  edit|focused|extended) ;;
  *)
    echo "check-runner.sh: CHECK_PROFILE must be edit, focused, or extended; got '$profile'" >&2
    exit 2
    ;;
esac

jobs_requested="${CHECK_JOBS:-auto}"
case "$jobs_requested" in
  auto) ;;
  *[!0-9]*|0|"")
    echo "check-runner.sh: CHECK_JOBS must be auto or a positive integer; got '$jobs_requested'" >&2
    exit 2
    ;;
esac

repo_lock_mode="${CHECK_REPO_LOCK:-enforce}"
case "$repo_lock_mode" in
  off|warn|enforce) ;;
  *)
    echo "check-runner.sh: CHECK_REPO_LOCK must be off, warn, or enforce; got '$repo_lock_mode'" >&2
    exit 2
    ;;
esac

repo_lock_held=false
repo_lock_owner=""
jobs_owner=""
tmp_latest=""
time_metrics=""
stage_events=""
# Both codes say the same thing about a trap handler, and which one you get depends on the
# linter's version: newer builds flag the function (SC2329, "never invoked"), while the older
# build preinstalled on the CI runners flags each line inside it (SC2317, "appears to be
# unreachable"). Disable both, or this gate passes locally and fails in CI.
# shellcheck disable=SC2317,SC2329 # invoked through the EXIT trap
cleanup() {
  [[ -n "$tmp_latest" ]] && rm -f "$tmp_latest"
  [[ -n "$time_metrics" ]] && rm -f "$time_metrics"
  [[ -n "$stage_events" ]] && rm -f "$stage_events"
  if [[ -n "$jobs_owner" && -f "$jobs_owner" ]] \
    && grep -qx "owner_pid=$$" "$jobs_owner"; then
    rm -f "$jobs_owner"
  fi
  if [[ "$repo_lock_held" == "true" && -f "$repo_lock_owner" ]] \
    && grep -qx "owner_pid=$$" "$repo_lock_owner"; then
    rm -f "$repo_lock_owner"
  fi
}
trap cleanup EXIT

git_common_dir="$(git rev-parse --git-common-dir)"
git_common_dir="$(cd "$git_common_dir" && pwd -P)"
git_worktree="$(git rev-parse --show-toplevel)"
git_worktree="$(cd "$git_worktree" && pwd -P)"
lock_relevant=false
if [[ "$profile" == "edit" || "$profile" == "extended" ]]; then
  lock_relevant=true
fi

cpu_count=""
if command -v sysctl >/dev/null 2>&1; then
  cpu_count="$(sysctl -n hw.ncpu 2>/dev/null || true)"
fi
if [[ ! "$cpu_count" =~ ^[1-9][0-9]*$ ]] && command -v getconf >/dev/null 2>&1; then
  cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || true)"
fi
[[ "$cpu_count" =~ ^[1-9][0-9]*$ ]] || cpu_count=1
jobs_budget=$((cpu_count - 4))
((jobs_budget > 0)) || jobs_budget=1
repo_name="$(basename "$git_worktree")"
case "$repo_name" in
  Atlas*) jobs_cap=12 ;;
  Clash*|Seraph*) jobs_cap=8 ;;
  *) jobs_cap=5 ;;
esac
jobs_cooperative=true
jobs_allocated="$jobs_cap"
if ((jobs_allocated > jobs_budget)); then
  jobs_allocated="$jobs_budget"
fi
if [[ "$jobs_requested" != "auto" && "$jobs_requested" -lt "$jobs_allocated" ]]; then
  jobs_allocated="$jobs_requested"
fi
if [[ "$profile" == "focused" || -n "${CI:-}" ]]; then
  jobs_cooperative=false
else
  jobs_root="${XDG_CACHE_HOME:-$HOME/.cache}/zion/check-jobs"
  jobs_owners="${jobs_root}/owners"
  if mkdir -p "$jobs_owners" && command -v flock >/dev/null 2>&1; then
    exec {jobs_lock_fd}>"${jobs_root}/allocation.lock"
    if flock -n "$jobs_lock_fd"; then
      jobs_in_use=0
      for owner in "$jobs_owners"/*.owner; do
        [[ -f "$owner" ]] || continue
        owner_pid="$(awk -F= '$1 == "owner_pid" {print $2; exit}' "$owner")"
        owner_jobs="$(awk -F= '$1 == "allocated" {print $2; exit}' "$owner")"
        if [[ ! "$owner_pid" =~ ^[1-9][0-9]*$ ]] || ! kill -0 "$owner_pid" 2>/dev/null; then
          rm -f "$owner"
        elif [[ "$owner_jobs" =~ ^[1-9][0-9]*$ ]]; then
          jobs_in_use=$((jobs_in_use + owner_jobs))
        fi
      done
      jobs_available=$((jobs_budget - jobs_in_use))
      ((jobs_available > 0)) || jobs_available=1
      if ((jobs_allocated > jobs_available)); then
        jobs_allocated="$jobs_available"
      fi
      jobs_owner="${jobs_owners}/$$.owner"
      jobs_owner_tmp="${jobs_owner}.tmp"
      umask 077
      {
        echo "owner_pid=$$"
        echo "requested=$jobs_requested"
        echo "allocated=$jobs_allocated"
        echo "budget=$jobs_budget"
        echo "profile=$profile"
        echo "worktree=$git_worktree"
        echo "common_dir=$git_common_dir"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      } > "$jobs_owner_tmp"
      mv "$jobs_owner_tmp" "$jobs_owner"
      flock -u "$jobs_lock_fd"
    else
      jobs_allocated=1
    fi
    exec {jobs_lock_fd}>&-
  else
    jobs_allocated=1
  fi
fi
export CHECK_JOBS="$jobs_allocated"
echo "CHECK_JOBS requested=${jobs_requested} allocated=${jobs_allocated} budget=${jobs_budget} cooperative=${jobs_cooperative}"
if [[ "$repo_lock_mode" != "off" && "$lock_relevant" == "true" && -z "${CI:-}" ]]; then
  if [[ "${CHECK_REPO_LOCK_ACTIVE:-}" == "$git_common_dir" ]]; then
    echo "CHECK_REPO_LOCK nested-bypass common_dir=${git_common_dir} profile=${profile}"
  elif ! command -v flock >/dev/null 2>&1; then
    echo "CHECK_REPO_LOCK unavailable mode=${repo_lock_mode} common_dir=${git_common_dir}" >&2
    [[ "$repo_lock_mode" == "enforce" ]] && exit 75
  else
    repo_lock_path="${git_common_dir}/check-runner.lock"
    repo_lock_owner="${git_common_dir}/check-runner.lock.owner"
    exec {repo_lock_fd}>"$repo_lock_path"
    if flock -n "$repo_lock_fd"; then
      repo_lock_held=true
      export CHECK_REPO_LOCK_ACTIVE="$git_common_dir"
      owner_tmp="${repo_lock_owner}.tmp.$$"
      umask 077
      {
        echo "owner_pid=$$"
        echo "profile=$profile"
        echo "worktree=$(git rev-parse --show-toplevel)"
        echo "common_dir=$git_common_dir"
        echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'command='
        printf '%q ' "$@"
        printf '\n'
      } > "$owner_tmp"
      mv "$owner_tmp" "$repo_lock_owner"
      echo "CHECK_REPO_LOCK acquired owner_pid=$$ common_dir=${git_common_dir} profile=${profile}"
    else
      echo "CHECK_REPO_LOCK denied mode=${repo_lock_mode} common_dir=${git_common_dir} profile=${profile}" >&2
      if [[ -f "$repo_lock_owner" ]]; then
        sed 's/^/CHECK_REPO_LOCK owner /' "$repo_lock_owner" >&2
      else
        echo "CHECK_REPO_LOCK owner metadata=unavailable" >&2
      fi
      exec {repo_lock_fd}>&-
      [[ "$repo_lock_mode" == "enforce" ]] && exit 75
    fi
  fi
fi

mkdir -p .check-runs

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
    for gate_tool in shellcheck luac stylua luacheck; do
      if git grep -Eq "(^|[^[:alnum:]_-])${gate_tool}([^[:alnum:]_-]|$)" -- \
        'check.sh' 'scripts/check*.sh' 2>/dev/null; then
        if command -v "$gate_tool" >/dev/null 2>&1; then
          printf '%s-path: %s\n' "$gate_tool" "$(command -v "$gate_tool")"
          printf '%s-version:\n' "$gate_tool"
          case "$gate_tool" in
            shellcheck|stylua|luacheck) "$gate_tool" --version 2>&1 || true ;;
            luac) "$gate_tool" -v 2>&1 || true ;;
          esac
        else
          printf '%s unavailable\n' "$gate_tool"
        fi
      fi
    done
  } | hash_stream
}

dependency_fingerprint() {
  while IFS= read -r dependency_file; do
    printf '%s\n' "$dependency_file"
    hash_file "$dependency_file"
  done < <(
    git ls-files \
      | awk -F/ '
          $NF == "uv.lock" || $NF == "pyproject.toml" ||
          $NF ~ /^requirements.*\.txt$/ ||
          $NF == "package-lock.json" || $NF == "npm-shrinkwrap.json" ||
          $NF == "pnpm-lock.yaml" || $NF == "yarn.lock" ||
          $NF == "Cargo.lock" || $NF == "go.sum" ||
          $NF == "poetry.lock" || $NF == "Pipfile.lock" ||
          $NF == ".python-version" || $NF == ".node-version" || $NF == ".nvmrc" ||
          $NF == "rust-toolchain" || $NF == "rust-toolchain.toml"
        ' \
      | sort
  ) | hash_stream
}

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM:-0}"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
started_at_epoch="$(date -u +%s)"
started_at_ns="$("$(python_bin)" -c 'import time; print(time.time_ns())')"
git_head="$(git rev-parse HEAD)"
fingerprint_before="$(worktree_fingerprint)"
dependency_fingerprint_value="$(dependency_fingerprint)"
log_path=".check-runs/${run_id}.log"
receipt_path=".check-runs/${run_id}.json"
time_metrics=".check-runs/.time.${run_id}.tmp"
stage_events=".check-runs/.stages.${run_id}.tmp"
cache_allowed="${CHECK_RUN_CACHE_ALLOWED:-0}"
authoritative=false
if [[ "$profile" == "edit" && "${CHECK_AUTHORITATIVE:-1}" != "0" ]]; then
  authoritative=true
fi

run_check() {
  if [[ "$repo_lock_held" == "true" ]]; then
    exec {repo_lock_fd}>&-
  fi
  echo "CHECK_RUN_STARTED run_id=${run_id}"
  printf 'CHECK_RUN_COMMAND'
  printf ' %q' "$@"
  printf '\n'
  if /usr/bin/time -p -l -o "$time_metrics" true >/dev/null 2>&1; then
    /usr/bin/time -p -l -o "$time_metrics" env CHECK_RUNNER_ACTIVE=1 "$@"
  else
    CHECK_RUNNER_ACTIVE=1 "$@"
  fi
}

observe_stages() {
  local line stage_name started_ns
  while IFS= read -r line; do
    printf '%s\n' "$line"
    if [[ "$line" =~ ^===([[:space:]]+)(.+)([[:space:]]+)===$ ]]; then
      stage_name="${BASH_REMATCH[2]}"
      started_ns="$("$(python_bin)" -c 'import time; print(time.time_ns())')"
      printf '%s\t%s\n' "$started_ns" "$stage_name" >> "$stage_events"
    fi
  done
}

: > "$stage_events"
set +e
if [[ "$repo_lock_held" == "true" ]]; then
  run_check "$@" 2>&1 \
    | observe_stages {repo_lock_fd}>&- \
    | tee "$log_path" {repo_lock_fd}>&-
else
  run_check "$@" 2>&1 \
    | observe_stages \
    | tee "$log_path"
fi
status=${PIPESTATUS[0]}
echo "CHECK_RUN_FINISHED run_id=${run_id} exit_code=${status}" | tee -a "$log_path"
set -e

finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
finished_at_epoch="$(date -u +%s)"
finished_at_ns="$("$(python_bin)" -c 'import time; print(time.time_ns())')"
fingerprint_after="$(worktree_fingerprint)"
toolchain_fingerprint_value="$(toolchain_fingerprint)"

export CHECK_RECEIPT_RUN_ID="$run_id"
if [[ "$status" == "0" ]]; then
  CHECK_RECEIPT_OK=true
else
  CHECK_RECEIPT_OK=false
fi
export CHECK_RECEIPT_OK
export CHECK_RECEIPT_EXIT_CODE="$status"
export CHECK_RECEIPT_GIT_HEAD="$git_head"
export CHECK_RECEIPT_FINGERPRINT_BEFORE="$fingerprint_before"
export CHECK_RECEIPT_FINGERPRINT="$fingerprint_after"
export CHECK_RECEIPT_STARTED_AT="$started_at"
export CHECK_RECEIPT_FINISHED_AT="$finished_at"
export CHECK_RECEIPT_STARTED_AT_EPOCH="$started_at_epoch"
export CHECK_RECEIPT_FINISHED_AT_EPOCH="$finished_at_epoch"
export CHECK_RECEIPT_STARTED_AT_NS="$started_at_ns"
export CHECK_RECEIPT_FINISHED_AT_NS="$finished_at_ns"
export CHECK_RECEIPT_LOG_PATH="$log_path"
export CHECK_RECEIPT_CACHE_ALLOWED="$cache_allowed"
export CHECK_RECEIPT_PROFILE="$profile"
export CHECK_RECEIPT_AUTHORITATIVE="$authoritative"
export CHECK_RECEIPT_TIME_METRICS="$time_metrics"
export CHECK_RECEIPT_STAGE_EVENTS="$stage_events"
export CHECK_RECEIPT_JOBS_REQUESTED="$jobs_requested"
export CHECK_RECEIPT_JOBS_ALLOCATED="$jobs_allocated"
export CHECK_RECEIPT_JOBS_BUDGET="$jobs_budget"
export CHECK_RECEIPT_JOBS_COOPERATIVE="$jobs_cooperative"
export CHECK_RECEIPT_GIT_COMMON_DIR="$git_common_dir"
export CHECK_RECEIPT_GIT_WORKTREE="$git_worktree"
export CHECK_RECEIPT_TOOLCHAIN_FINGERPRINT="$toolchain_fingerprint_value"
export CHECK_RECEIPT_DEPENDENCY_FINGERPRINT="$dependency_fingerprint_value"
# Same rule as the latest.json publish below, and this is the larger surface: under set -e a
# raising receipt writer would exit with the writer's status and skip the final `exit "$status"`,
# reporting a passing check as failed. The writer is evidence about the run; it must never be
# able to change the run's verdict.
set +e
"$(python_bin)" - "$receipt_path" "$@" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

receipt_path = sys.argv[1]
resource = None
# None, not 0.0: the rusage probe is BSD-only, so a Linux runner never writes this file and a
# 0.0 default would assert a measured zero for a check that burned CPU. Missing stays missing.
cpu_duration = None
peak_rss = None
metrics_path = Path(os.environ["CHECK_RECEIPT_TIME_METRICS"])
if metrics_path.is_file():
    user = None
    system = None
    for line in metrics_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        # One file, two shapes: `-p` emits label first ("user 0.41"), while the `-l` rusage
        # block emits value first ("999616  peak memory footprint"). Reading every line as
        # value-first left `label` holding the number, so no user/sys line ever matched and
        # cpu_duration was always 0.0 while peak_rss parsed fine.
        first, second = parts
        label, value = (first, second) if first in ("real", "user", "sys") else (second, first)
        if label == "user":
            user = float(value)
        elif label == "sys":
            system = float(value)
        elif label == "peak memory footprint" and value.isdigit():
            peak_rss = int(value)
    if user is not None and system is not None:
        cpu_duration = user + system
finished_at_ns = int(os.environ["CHECK_RECEIPT_FINISHED_AT_NS"])
stage_events_path = Path(os.environ["CHECK_RECEIPT_STAGE_EVENTS"])
stage_events = []
if stage_events_path.is_file():
    for line in stage_events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            started_at_ns, name = line.split("\t", 1)
            event = {"name": name.strip(), "started_at_ns": int(started_at_ns)}
        except (ValueError, TypeError):
            continue
        if isinstance(event.get("name"), str) and isinstance(event.get("started_at_ns"), int):
            stage_events.append(event)
stage_outcomes = []
name_counts = {}
for index, event in enumerate(stage_events):
    raw_name = event["name"]
    name_counts[raw_name] = name_counts.get(raw_name, 0) + 1
    name = raw_name
    if name_counts[raw_name] > 1:
        name = f"{raw_name} #{name_counts[raw_name]}"
    end_ns = (
        stage_events[index + 1]["started_at_ns"]
        if index + 1 < len(stage_events)
        else finished_at_ns
    )
    stage_outcomes.append(
        {
            "name": name,
            "status": (
                "fail"
                if os.environ["CHECK_RECEIPT_OK"] != "true" and index + 1 == len(stage_events)
                else "pass"
            ),
            "duration_seconds": max(0, end_ns - event["started_at_ns"]) / 1_000_000_000,
        }
    )
if not stage_outcomes:
    stage_outcomes = [
        {
            "name": "command",
            "status": "pass" if os.environ["CHECK_RECEIPT_OK"] == "true" else "fail",
            "duration_seconds": (
                finished_at_ns - int(os.environ["CHECK_RECEIPT_STARTED_AT_NS"])
            )
            / 1_000_000_000,
        }
    ]

sibling_commits = []
manifest_root = Path.home() / ".local/state/zion/worktrees"
if manifest_root.is_dir():
    manifests = sorted(
        manifest_root.glob("*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for manifest in manifests:
        try:
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            bundle.get("worktree") != os.environ["CHECK_RECEIPT_GIT_WORKTREE"]
            or bundle.get("commit") != os.environ["CHECK_RECEIPT_GIT_HEAD"]
        ):
            continue
        for name, dependency in sorted(bundle.get("dependencies", {}).items()):
            resolved = subprocess.run(
                ["git", "-C", str(dependency.get("path", "")), "rev-parse", "HEAD"],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            sibling_commits.append(
                {
                    "name": name,
                    "expected": dependency.get("commit"),
                    "resolved": resolved.stdout.strip() if resolved.returncode == 0 else None,
                }
            )
        break
payload = {
    "schema_version": "check_receipt.v2",
    "ok": os.environ["CHECK_RECEIPT_OK"] == "true",
    "exit_code": int(os.environ["CHECK_RECEIPT_EXIT_CODE"]),
    "run_id": os.environ["CHECK_RECEIPT_RUN_ID"],
    "git_head": os.environ["CHECK_RECEIPT_GIT_HEAD"],
    "worktree_fingerprint_before": os.environ["CHECK_RECEIPT_FINGERPRINT_BEFORE"],
    "worktree_fingerprint": os.environ["CHECK_RECEIPT_FINGERPRINT"],
    "started_at": os.environ["CHECK_RECEIPT_STARTED_AT"],
    "finished_at": os.environ["CHECK_RECEIPT_FINISHED_AT"],
    "started_at_epoch": int(os.environ["CHECK_RECEIPT_STARTED_AT_EPOCH"]),
    "finished_at_epoch": int(os.environ["CHECK_RECEIPT_FINISHED_AT_EPOCH"]),
    "wall_duration_seconds": (
        int(os.environ["CHECK_RECEIPT_FINISHED_AT_NS"])
        - int(os.environ["CHECK_RECEIPT_STARTED_AT_NS"])
    ) / 1_000_000_000,
    "cpu_duration_seconds": cpu_duration,
    "peak_rss_bytes": peak_rss,
    "log_path": os.environ["CHECK_RECEIPT_LOG_PATH"],
    "cache_allowed": os.environ["CHECK_RECEIPT_CACHE_ALLOWED"] == "1",
    "profile": os.environ["CHECK_RECEIPT_PROFILE"],
    "authoritative": os.environ["CHECK_RECEIPT_AUTHORITATIVE"] == "true",
    "resource": resource,
    "worker_allocation": {
        "requested": os.environ["CHECK_RECEIPT_JOBS_REQUESTED"],
        "allocated": int(os.environ["CHECK_RECEIPT_JOBS_ALLOCATED"]),
        "budget": int(os.environ["CHECK_RECEIPT_JOBS_BUDGET"]),
        "cooperative": os.environ["CHECK_RECEIPT_JOBS_COOPERATIVE"] == "true",
    },
    "stage_outcomes": stage_outcomes,
    "git_common_dir": os.environ["CHECK_RECEIPT_GIT_COMMON_DIR"],
    "git_worktree": os.environ["CHECK_RECEIPT_GIT_WORKTREE"],
    "toolchain_fingerprint": os.environ["CHECK_RECEIPT_TOOLCHAIN_FINGERPRINT"],
    "dependency_fingerprint": os.environ["CHECK_RECEIPT_DEPENDENCY_FINGERPRINT"],
    "sibling_commits": sibling_commits,
    "command": sys.argv[2:],
}
with open(receipt_path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
receipt_status=$?
set -e
if [[ "$receipt_status" != "0" ]]; then
  echo "check-runner.sh: warning: failed to write receipt (exit ${receipt_status})" >&2
fi

# Atomic publish: `cp` onto the well-known latest.json is not — a kill mid-copy leaves it
# truncated, and check-status.sh's json.loads() then raises a raw traceback instead of a clean
# "no current receipt" message (2026-07-05 review finding, originally caught on Atlas). `mv`
# within .check-runs/ is a rename, atomic on the same filesystem — readers always see either
# the prior latest.json or the new one, never a partial write.
tmp_latest=".check-runs/.latest.json.tmp.$$"
# A process killed (or a cp failure) between the cp and the mv would otherwise leave the tmp file
# orphaned in .check-runs/; clean it on exit. After a successful mv the tmp no longer exists, so
# the rm -f is a harmless no-op.
# Never let a publish failure mask the real check exit code: under set -e a failing cp/mv would
# exit with the copy/move's status and skip the final `exit "$status"`. Disable set -e around the
# publish, warn on failure, and always exit with the check's own status.
# Gated on the writer having succeeded: a writer that dies mid-json.dump leaves a truncated
# receipt at $receipt_path, and publishing it would atomically install corrupt JSON as the
# well-known latest.json — exactly the failure the atomic rename exists to prevent. The prior
# latest.json (a complete receipt for an older run) is strictly better evidence than a partial
# one for this run.
if [[ "$authoritative" == "true" && "$receipt_status" == "0" ]]; then
  set +e
  cp "$receipt_path" "$tmp_latest" && mv "$tmp_latest" .check-runs/latest.json
  publish_status=$?
  set -e
  if [[ "$publish_status" != "0" ]]; then
    echo "check-runner.sh: warning: failed to publish latest.json (exit ${publish_status})" >&2
  fi
fi
exit "$status"
