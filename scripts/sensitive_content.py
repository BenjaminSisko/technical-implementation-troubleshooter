#!/usr/bin/env python3
"""Shared high-confidence secret detection and reviewed redaction helpers."""

from __future__ import annotations

import re


DETECTOR_PATTERNS = {
    "private_key_block": re.compile(
        rb"-----BEGIN (?:(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----"
    ),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "github_fine_grained_token": re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    "gitlab_token": re.compile(rb"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "slack_token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "aws_access_key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_token": re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~-]{24,}\b"),
}

PRIVATE_KEY_BLOCK_RE = re.compile(
    rb"-----BEGIN (?P<label>(?:(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY|PGP PRIVATE KEY BLOCK))-----"
    rb".*?"
    rb"-----END (?P=label)-----",
    re.DOTALL,
)

REDACTION_PATTERNS = {
    "private_key_block": PRIVATE_KEY_BLOCK_RE,
    "github_token": DETECTOR_PATTERNS["github_token"],
    "github_fine_grained_token": DETECTOR_PATTERNS["github_fine_grained_token"],
    "gitlab_token": DETECTOR_PATTERNS["gitlab_token"],
    "slack_token": DETECTOR_PATTERNS["slack_token"],
    "aws_access_key": DETECTOR_PATTERNS["aws_access_key"],
    "bearer_token": DETECTOR_PATTERNS["bearer_token"],
}

REDACTION_MARKERS = {
    "private_key_block": b"[REDACTED_REVIEWED_PRIVATE_KEY_EXAMPLE]",
    "github_token": b"[REDACTED_REVIEWED_GITHUB_TOKEN_EXAMPLE]",
    "github_fine_grained_token": b"[REDACTED_REVIEWED_GITHUB_TOKEN_EXAMPLE]",
    "gitlab_token": b"[REDACTED_REVIEWED_GITLAB_TOKEN_EXAMPLE]",
    "slack_token": b"[REDACTED_REVIEWED_SLACK_TOKEN_EXAMPLE]",
    "aws_access_key": b"[REDACTED_REVIEWED_AWS_ACCESS_KEY_EXAMPLE]",
    "bearer_token": b"Bearer [REDACTED_REVIEWED_BEARER_TOKEN_EXAMPLE]",
}


def detect_secret_types(raw: bytes) -> list[str]:
    """Return stable detector names without returning any matched values."""

    return sorted(
        name for name, pattern in DETECTOR_PATTERNS.items() if pattern.search(raw)
    )


def has_high_confidence_secret(raw: bytes) -> bool:
    return bool(detect_secret_types(raw))


def redact_approved_content(
    raw: bytes, approved_detectors: set[str]
) -> tuple[bytes, dict[str, int]]:
    """Redact only explicitly approved detector classes from reviewed content."""

    unknown = approved_detectors - set(REDACTION_PATTERNS)
    if unknown:
        raise ValueError(f"unknown approved detectors: {', '.join(sorted(unknown))}")
    sanitized = raw
    counts: dict[str, int] = {}
    for detector in sorted(approved_detectors):
        sanitized, count = REDACTION_PATTERNS[detector].subn(
            REDACTION_MARKERS[detector], sanitized
        )
        counts[detector] = count
    return sanitized, counts
