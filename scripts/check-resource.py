#!/usr/bin/env python3
"""Serialize local desktop checks and export a conservative resource budget.

The wrapper is deliberately process-local: it holds an inherited ``fcntl`` lock while
the original command executes, rather than maintaining a daemon or sharing any test
or database state between repositories.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn


@dataclass(frozen=True)
class HostSnapshot:
    cpu_idle: float | None
    memory_free_percent: int | None
    gpu_utilization: int | None
    battery_percent: int | None
    thermal_warning: bool | None


@dataclass(frozen=True)
class ResourceProfile:
    mode: str
    host_class: str | None
    workers: int | None
    static_lanes: int | None
    wait_ms: int | None
    taskpolicy_applied: bool


def _command_output(command: Sequence[str]) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, check=False).stdout
    except OSError:
        return ""


def collect_host_snapshot() -> HostSnapshot:
    top_output = _command_output(["top", "-l", "2", "-s", "1", "-n", "0"])
    idle_matches = re.findall(r"([0-9.]+)%\s+idle", top_output)
    cpu_idle = float(idle_matches[-1]) if idle_matches else None

    memory_output = _command_output(["memory_pressure"])
    memory_match = re.search(r"memory free percentage:\s*(\d+)%", memory_output, re.IGNORECASE)
    memory_free = int(memory_match.group(1)) if memory_match else None

    gpu_output = _command_output(["ioreg", "-l"])
    gpu_match = re.search(r'"Device Utilization %"\s*=\s*(\d+)', gpu_output)
    gpu_utilization = int(gpu_match.group(1)) if gpu_match else None

    battery_output = _command_output(["pmset", "-g", "batt"])
    battery_match = re.search(r"(\d+)%", battery_output)
    battery_percent = int(battery_match.group(1)) if battery_match else None

    therm_output = _command_output(["pmset", "-g", "therm"])
    if not therm_output:
        thermal_warning = None
    else:
        thermal_warning = bool(
            re.search(r"(?:thermal|performance|cpu) warning level[^0-9]*[1-9]", therm_output, re.I)
        )

    return HostSnapshot(
        cpu_idle=cpu_idle,
        memory_free_percent=memory_free,
        gpu_utilization=gpu_utilization,
        battery_percent=battery_percent,
        thermal_warning=thermal_warning,
    )


def snapshot_for_environment(env: Mapping[str, str]) -> HostSnapshot:
    test_class = env.get("CHECK_RESOURCE_TEST_CLASS")
    if test_class == "normal":
        return HostSnapshot(80.0, 40, 10, 80, False)
    if test_class == "constrained":
        return HostSnapshot(20.0, 10, 90, 10, True)
    return collect_host_snapshot()


def choose_profile(env: Mapping[str, str], snapshot: HostSnapshot) -> ResourceProfile:
    mode = env.get("CHECK_RESOURCE_MODE", "desktop")
    if mode == "off" or env.get("CI"):
        return ResourceProfile(
            mode=mode,
            host_class=None,
            workers=None,
            static_lanes=None,
            wait_ms=None,
            taskpolicy_applied=False,
        )
    if mode == "burst":
        return ResourceProfile(
            mode=mode,
            host_class="burst",
            workers=12,
            static_lanes=4,
            wait_ms=None,
            taskpolicy_applied=False,
        )
    if mode != "desktop":
        raise ValueError(f"CHECK_RESOURCE_MODE must be desktop, burst, or off; got {mode!r}")

    test_class = env.get("CHECK_RESOURCE_TEST_CLASS")
    if test_class not in {None, "normal", "constrained"}:
        raise ValueError(
            f"CHECK_RESOURCE_TEST_CLASS must be normal or constrained; got {test_class!r}"
        )
    if test_class == "normal":
        return ResourceProfile(
            mode=mode,
            host_class="normal",
            workers=8,
            static_lanes=2,
            wait_ms=None,
            taskpolicy_applied=False,
        )
    if test_class == "constrained":
        return ResourceProfile(
            mode=mode,
            host_class="constrained",
            workers=4,
            static_lanes=1,
            wait_ms=None,
            taskpolicy_applied=False,
        )

    normal = (
        snapshot.cpu_idle is not None
        and snapshot.cpu_idle >= 70
        and snapshot.memory_free_percent is not None
        and snapshot.memory_free_percent >= 20
        and snapshot.gpu_utilization is not None
        and snapshot.gpu_utilization < 70
        and snapshot.battery_percent is not None
        and snapshot.battery_percent >= 25
        and snapshot.thermal_warning is not True
    )
    if normal:
        return ResourceProfile(
            mode=mode,
            host_class="normal",
            workers=8,
            static_lanes=2,
            wait_ms=None,
            taskpolicy_applied=False,
        )
    return ResourceProfile(
        mode=mode,
        host_class="constrained",
        workers=4,
        static_lanes=1,
        wait_ms=None,
        taskpolicy_applied=False,
    )


def _state_dir(env: Mapping[str, str]) -> Path:
    configured = env.get("CHECK_RESOURCE_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library" / "Caches" / "zion" / "check-fleet"


def _exec(command: Sequence[str], env: Mapping[str, str], *, taskpolicy: bool) -> NoReturn:
    argv = list(command)
    if taskpolicy:
        argv = ["/usr/sbin/taskpolicy", "-b", *argv]
    try:
        os.execvpe(argv[0], argv, dict(env))
    except OSError as exc:
        print(f"check-resource: failed to execute {argv[0]}: {exc}", file=sys.stderr)
        raise SystemExit(127) from exc


def acquire_and_exec(command: Sequence[str], env: Mapping[str, str]) -> NoReturn:
    if not command:
        print("usage: check-resource.py -- <command> [args...]", file=sys.stderr)
        raise SystemExit(2)
    if env.get("CHECK_RESOURCE_ACTIVE") == "1":
        _exec(command, env, taskpolicy=False)

    profile = choose_profile(env, snapshot_for_environment(env))
    if profile.workers is None:
        _exec(command, env, taskpolicy=False)
    if env.get("CHECK_RESOURCE_REQUIRE_NORMAL") == "1" and profile.host_class != "normal":
        print("check-resource: benchmark requires a normal host", file=sys.stderr)
        raise SystemExit(75)

    lock_path = _state_dir(env) / "desktop.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        started = time.monotonic()
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        wait_ms = int((time.monotonic() - started) * 1000)
        os.set_inheritable(lock_file.fileno(), True)
        next_env = dict(env)
        next_env.update(
            {
                "CHECK_RESOURCE_ACTIVE": "1",
                "CHECK_RESOURCE_MODE": profile.mode,
                "CHECK_RESOURCE_CLASS": profile.host_class or "",
                "CHECK_RESOURCE_WORKERS": str(profile.workers),
                "CHECK_RESOURCE_STATIC_LANES": str(profile.static_lanes),
                "CHECK_RESOURCE_WAIT_MS": str(wait_ms),
                "CHECK_RESOURCE_LOCK_FD": str(lock_file.fileno()),
            }
        )
        use_taskpolicy = (
            sys.platform == "darwin"
            and profile.host_class == "constrained"
            and not env.get("CHECK_RESOURCE_TEST_NO_TASKPOLICY")
            and Path("/usr/sbin/taskpolicy").is_file()
            and shutil.which("taskpolicy") is not None
        )
        next_env["CHECK_RESOURCE_TASKPOLICY_APPLIED"] = "1" if use_taskpolicy else "0"
        _exec(command, next_env, taskpolicy=use_taskpolicy)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "--":
        print("usage: check-resource.py -- <command> [args...]", file=sys.stderr)
        return 2
    acquire_and_exec(args[1:], os.environ)
    raise AssertionError("acquire_and_exec must exec or exit")


if __name__ == "__main__":
    raise SystemExit(main())
