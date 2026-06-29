#!/usr/bin/env python3
"""Offline environment report for bioscientist-os.

Stdlib-only and read-only: it makes no network calls, installs nothing, and
reads no secrets. Run it before/after setting up a virtualenv to confirm the host
can build and test the workbench on CPU.

    python3 scripts/00_check_environment.py
    python3 scripts/00_check_environment.py --json

Exit status is non-zero only on a hard blocker (e.g. Python older than 3.12).
Missing optional packages are reported as INFO, not failures, since the default
test path is dependency-light and several deps are optional extras.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
from dataclasses import asdict, dataclass, field

MIN_PYTHON = (3, 12)

# (import name, why it matters, is it required for the *default* path)
PACKAGES = [
    ("pydantic", "typed schemas (core)", True),
    ("typer", "CLI (core)", True),
    ("pandas", "analysis tables (core)", True),
    ("networkx", "relation graphs (core)", True),
    ("pytest", "test runner (dev)", False),
    ("ruff", "linter (dev)", False),
    ("matplotlib", "figures (optional extra: viz)", False),
    ("duckdb", "optional storage backend (extra: duckdb)", False),
    ("anthropic", "opt-in real LLM adapter (extra: llm)", False),
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class Report:
    python_version: str
    platform: str
    cpu_count: int | None
    cwd: str
    checks: list[Check] = field(default_factory=list)

    @property
    def hard_ok(self) -> bool:
        return all(c.ok for c in self.checks if c.name.startswith("required:"))


def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def _disk_free_gb(path: str) -> float | None:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / (1024**3), 1)
    except OSError:
        return None


def run_checks() -> Report:
    rep = Report(
        python_version=platform.python_version(),
        platform=platform.platform(),
        cpu_count=os.cpu_count(),
        cwd=os.getcwd(),
    )

    # Required: Python version.
    py_ok = sys.version_info[:2] >= MIN_PYTHON
    rep.checks.append(
        Check(
            name="required:python>=3.12",
            ok=py_ok,
            detail=f"found {platform.python_version()}, need >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
        )
    )

    # Required core packages.
    for mod, why, required in PACKAGES:
        present = _has(mod)
        prefix = "required" if required else "optional"
        rep.checks.append(
            Check(
                name=f"{prefix}:import {mod}",
                ok=present or not required,
                detail=("present" if present else "missing") + f"  — {why}",
            )
        )

    # Tooling (informational).
    for tool in ("git", "claude", "sqlite3"):
        path = shutil.which(tool)
        rep.checks.append(
            Check(
                name=f"info:tool {tool}",
                ok=True,
                detail=path or "not found on PATH",
            )
        )

    # Disk headroom (informational; fixtures + results are tiny).
    free = _disk_free_gb(os.getcwd())
    rep.checks.append(
        Check(
            name="info:disk_free_gb",
            ok=True,
            detail=f"{free} GB free" if free is not None else "unknown",
        )
    )

    # Offline-by-default reminder (informational).
    rep.checks.append(
        Check(
            name="info:network",
            ok=True,
            detail="default path requires no network or paid API",
        )
    )
    return rep


def format_text(rep: Report) -> str:
    lines = [
        "bioscientist-os — environment report",
        "=" * 44,
        f"python   : {rep.python_version}",
        f"platform : {rep.platform}",
        f"cpu_count: {rep.cpu_count}",
        f"cwd      : {rep.cwd}",
        "",
        "checks:",
    ]
    for c in rep.checks:
        mark = "PASS" if c.ok else "FAIL"
        lines.append(f"  [{mark}] {c.name:<28} {c.detail}")
    lines.append("")
    lines.append("RESULT: " + ("OK (host can build and test on CPU)" if rep.hard_ok else "BLOCKED (see FAILs above)"))
    if not rep.hard_ok:
        lines.append("Hint: create a venv and install deps:  pip install -e '.[dev]'")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline environment report.")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    rep = run_checks()
    if args.json:
        payload = asdict(rep)
        payload["hard_ok"] = rep.hard_ok
        print(json.dumps(payload, indent=2))
    else:
        print(format_text(rep))
    return 0 if rep.hard_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
