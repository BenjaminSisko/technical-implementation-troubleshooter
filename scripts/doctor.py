#!/usr/bin/env python3
"""Run offline readiness checks for the troubleshooting skill."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from activate_corpus import (
    DEFAULT_CONFIG,
    MINIMUM_PYTHON,
    fts5_available,
    load_config,
    validate_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check troubleshooting-skill readiness.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    python_ok = sys.version_info >= MINIMUM_PYTHON
    add(
        "python-version",
        python_ok,
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    sqlite_ok, sqlite_reason = fts5_available()
    add("sqlite-fts5", sqlite_ok, sqlite3.sqlite_version if sqlite_ok else str(sqlite_reason))

    config_path = args.config.expanduser().resolve()
    config_valid = True
    try:
        config, exists = load_config(config_path)
    except ValueError as exc:
        config, exists = {}, True
        config_valid = False
        add("configuration", False, str(exc))
    else:
        add("configuration", exists, str(config_path) if exists else "missing")

    issues: list[str] = []
    warnings: list[str] = []
    permissions_ok = False
    if exists and config:
        issues, warnings = validate_config(config, require_ready=True)
        add("configured-roots-and-indexes", not issues, "; ".join(issues) or "ready")
        mode = os.stat(config_path).st_mode & 0o777
        permissions_ok = mode & 0o077 == 0
        add("configuration-permissions", permissions_ok, oct(mode))

    passed = (
        python_ok
        and sqlite_ok
        and exists
        and config_valid
        and permissions_ok
        and not issues
    )
    output = {
        "status": "READY" if passed else "NOT_READY",
        "config": str(config_path),
        "checks": checks,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"status={output['status']} config={config_path}")
        for check in checks:
            marker = "PASS" if check["passed"] else "FAIL"
            print(f"[{marker}] {check['name']}: {check['detail']}")
        for warning in warnings:
            print(f"[WARN] {warning}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
