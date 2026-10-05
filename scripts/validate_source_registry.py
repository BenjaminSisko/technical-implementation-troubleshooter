#!/usr/bin/env python3
"""Validate the portable primary-source registry without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
AUTHORITY = {
    "vendor-primary",
    "vendor-security",
    "vendor-source",
    "standards-primary",
    "organization-approved",
    "live-evidence",
}
ACCESS = {
    "public-anonymous",
    "public-account-required",
    "subscription-entitled",
    "developer-login-required",
    "organization-internal",
}
REDISTRIBUTION = {
    "public-permitted",
    "public-with-attribution",
    "public-share-alike",
    "metadata-only-public",
    "local-use-only",
    "manual-license-review",
    "unknown-quarantine",
}
CLASSIFICATION = {"public", "private", "restricted"}
ACQUISITION = {
    "public-web",
    "authenticated-user-download",
    "package-repository-sync",
    "source-checkout",
    "local-command-export",
    "manual-media-import",
}
STATUS = {"candidate", "active", "retired"}
REQUIRED_TEXT = {
    "source_id",
    "vendor",
    "product",
    "domain",
    "title",
    "canonical_url",
    "source_authority",
    "access_class",
    "redistribution_class",
    "default_classification",
    "acquisition_mode",
    "refresh_cadence",
    "status",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a source-registry JSON file.")
    parser.add_argument("registry", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = json.loads(args.registry.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read registry: {exc}", file=sys.stderr)
        return 2
    errors: list[str] = []
    if not isinstance(payload, dict):
        print("error: registry root must be an object", file=sys.stderr)
        return 2
    if payload.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    for field in ("registry_id", "as_of"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            errors.append(f"{field} must be a non-empty string")
    try:
        date.fromisoformat(payload.get("as_of", ""))
    except (TypeError, ValueError):
        errors.append("as_of must be an ISO date")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty array")
        sources = []
    identifiers: set[str] = set()
    allowed_fields = REQUIRED_TEXT | {
        "version_strategy",
        "applicability",
        "parser_hint",
        "notes",
    }
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        unknown = set(source) - allowed_fields
        if unknown:
            errors.append(f"{prefix} has unknown fields: {', '.join(sorted(unknown))}")
        for field in REQUIRED_TEXT:
            if not isinstance(source.get(field), str) or not source[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        source_id = source.get("source_id")
        if isinstance(source_id, str):
            if not ID_RE.fullmatch(source_id):
                errors.append(f"{prefix}.source_id has invalid syntax")
            if source_id in identifiers:
                errors.append(f"duplicate source_id: {source_id}")
            identifiers.add(source_id)
        parsed = urlparse(source.get("canonical_url", ""))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{prefix}.canonical_url must be an HTTPS URL")
        checks = (
            ("source_authority", AUTHORITY),
            ("access_class", ACCESS),
            ("redistribution_class", REDISTRIBUTION),
            ("default_classification", CLASSIFICATION),
            ("acquisition_mode", ACQUISITION),
            ("status", STATUS),
        )
        for field, allowed in checks:
            if source.get(field) not in allowed:
                errors.append(f"{prefix}.{field} is invalid")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(f"validation failed: {len(errors)} error(s)")
        return 1
    print(f"validation passed: sources={len(sources)} registry={payload['registry_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
