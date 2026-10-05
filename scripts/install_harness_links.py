#!/usr/bin/env python3
"""Expose one skill checkout to Codex and Claude Code without duplicate copies."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


SKILL_NAME = "technical-implementation-troubleshooter"
DEFAULT_SOURCE = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link one skill checkout into Codex and Claude Code skill roots."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex" / "skills")
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude" / "skills")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def ensure_link(source: Path, root: Path, dry_run: bool) -> tuple[bool, str]:
    destination = root.expanduser().resolve() / SKILL_NAME
    if destination.exists() or destination.is_symlink():
        try:
            existing = destination.resolve(strict=True)
        except OSError as exc:
            return False, f"broken or unreadable destination {destination}: {exc}"
        if existing == source:
            return True, f"already configured: {destination} -> {source}"
        return False, f"refusing to replace existing destination: {destination} -> {existing}"
    relative_target = os.path.relpath(source, destination.parent)
    if dry_run:
        return True, f"would link: {destination} -> {relative_target}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(relative_target, target_is_directory=True)
    return True, f"linked: {destination} -> {relative_target}"


def main() -> int:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not (source / "SKILL.md").is_file():
        print(f"error: source does not contain SKILL.md: {source}", file=sys.stderr)
        return 2
    failures = 0
    for root in (args.codex_root, args.claude_root):
        passed, message = ensure_link(source, root, args.dry_run)
        print(message, file=sys.stdout if passed else sys.stderr)
        failures += 0 if passed else 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
