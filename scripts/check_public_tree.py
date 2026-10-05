#!/usr/bin/env python3
"""Reject private/generated payloads and workstation facts from the Git tree."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
FORBIDDEN_DIRECTORIES = {
    "private-corpus",
    "vendor-bundles",
    "support-bundles",
    "host-captures",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".iso",
    ".jks",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".rpm",
    ".sqlite",
}
FORBIDDEN_NAME_SUFFIXES = {
    ".approval.json",
    ".documents.json",
    ".sanitization.json",
    ".sqlite.report.json",
}
OPERATIONAL_PATTERNS = {
    "macOS user path": re.compile(re.escape("/" + "Users/")),
    "macOS volume path": re.compile(re.escape("/" + "Volumes/")),
    "named Linux home path": re.compile(re.escape("/home/" + "benny/")),
    "private home-lab IPv4 address": re.compile(
        r"(?<![0-9])" + re.escape("192" + ".168.") + r"[0-9]{1,3}\.[0-9]{1,3}(?![0-9])"
    ),
}


def tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    files = tracked_files()
    for relative in files:
        path = Path(relative)
        if FORBIDDEN_DIRECTORIES.intersection(path.parts):
            findings.append(f"forbidden private directory: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden generated/private payload type: {relative}")
        if any(path.name.endswith(suffix) for suffix in FORBIDDEN_NAME_SUFFIXES):
            findings.append(f"forbidden private review artifact: {relative}")
        absolute = REPO / path
        if absolute.is_symlink():
            findings.append(f"tracked symbolic link requires publication review: {relative}")
            continue
        try:
            text = absolute.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            findings.append(f"cannot inspect tracked file {relative}: {exc}")
            continue
        for label, pattern in OPERATIONAL_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{label}: {relative}:{line}")

    if findings:
        for finding in findings:
            print(f"error: {finding}", file=sys.stderr)
        print(f"public-tree check failed: findings={len(findings)}", file=sys.stderr)
        return 1
    print(f"public-tree check passed: tracked_files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
