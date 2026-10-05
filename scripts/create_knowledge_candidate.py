#!/usr/bin/env python3
"""Create a reviewable knowledge-promotion candidate from a verified case record."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a candidate runbook/known-issue record. This never marks the "
            "candidate active and never rewrites the source case."
        )
    )
    parser.add_argument("--case-record", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--applicability", required=True)
    parser.add_argument("--resolution", required=True)
    parser.add_argument("--verification", required=True)
    parser.add_argument("--rollback", required=True)
    parser.add_argument(
        "--evidence",
        action="append",
        required=True,
        help="Verified evidence citation; repeat for multiple citations.",
    )
    parser.add_argument("--change-reference")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def quote_yaml(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:80] or "knowledge-candidate"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    args = parse_args()
    case_path = args.case_record.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not case_path.is_file() or case_path.is_symlink():
        print(f"error: case record must be a regular non-symlink file: {case_path}", file=sys.stderr)
        return 2
    if output.exists():
        print(f"error: candidate output already exists: {output}", file=sys.stderr)
        return 2
    case_hash = hashlib.sha256(case_path.read_bytes()).hexdigest()
    evidence_lines = "\n".join(f"- {value}" for value in args.evidence)
    content = f"""---
type: knowledge-candidate
status: candidate
title: {quote_yaml(args.title)}
created: {date.today().isoformat()}
applicability: {quote_yaml(args.applicability)}
source_case: {quote_yaml(case_path.name)}
source_case_sha256: {case_hash}
change_reference: {quote_yaml(args.change_reference) if args.change_reference else 'null'}
---

# {args.title}

## Review Gate

This is a candidate generated from a verified case. It is not active guidance until a reviewer confirms the evidence, version boundaries, command safety, rollback, and verification steps.

## Applicability

{args.applicability}

## Verified Evidence

{evidence_lines}

## Resolution

{args.resolution}

## Verification

{args.verification}

## Rollback or Recovery

{args.rollback}

## Promotion Checklist

- [ ] Source case and SHA-256 match the reviewed record.
- [ ] Product, OS, kernel, hardware, and dependent-version boundaries are explicit.
- [ ] Commands distinguish diagnostics from state changes.
- [ ] Security, blast radius, rollback, and persistence were reviewed.
- [ ] A second operator or designated reviewer approved activation.
- [ ] Corpus index and behavioral evaluations passed after promotion.
"""
    if args.dry_run:
        print(f"would create candidate={output} slug={slug(args.title)} case-sha256={case_hash}")
        return 0
    try:
        atomic_write(output, content)
    except OSError as exc:
        print(f"error: cannot write candidate: {exc}", file=sys.stderr)
        return 1
    print(f"created candidate={output} status=candidate case-sha256={case_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
