#!/usr/bin/env python3
"""Verify path safety and SHA-256 integrity for an offline vendor bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import urlparse


SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
VALID_STATUS = {"candidate", "active", "superseded"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an air-gapped vendor-reference bundle against its manifest."
    )
    parser.add_argument("--bundle", required=True, type=Path, help="Bundle root directory.")
    parser.add_argument("--manifest", required=True, type=Path, help="Manifest JSON path.")
    parser.add_argument("--signature", type=Path, help="Detached OpenPGP manifest signature.")
    parser.add_argument("--keyring", type=Path, help="Trusted public-key keyring for gpgv.")
    parser.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="Explicitly permit an unsigned development/personal bundle.",
    )
    parser.add_argument(
        "--strict-unlisted",
        action="store_true",
        help="Fail when regular bundle files are not listed in the manifest.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: object) -> Optional[PurePosixPath]:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    return relative


def valid_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> int:
    args = parse_args()
    bundle = args.bundle.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not bundle.is_dir():
        print(f"error: bundle is not a directory: {bundle}", file=sys.stderr)
        return 2
    if not manifest_path.is_file():
        print(f"error: manifest is not a file: {manifest_path}", file=sys.stderr)
        return 2

    signature_verified = False
    signature_path = args.signature.expanduser().resolve() if args.signature else None
    keyring_path = args.keyring.expanduser().resolve() if args.keyring else None
    if args.allow_unsigned:
        if signature_path or keyring_path:
            errors.append("--allow-unsigned cannot be combined with --signature or --keyring")
    else:
        if signature_path is None or keyring_path is None:
            errors.append(
                "a detached manifest --signature and trusted --keyring are required; "
                "use --allow-unsigned only for an explicitly accepted unsigned bundle"
            )
        elif not signature_path.is_file():
            errors.append(f"signature is not a file: {signature_path}")
        elif not keyring_path.is_file():
            errors.append(f"keyring is not a file: {keyring_path}")
        elif shutil.which("gpgv") is None:
            errors.append("gpgv is required for detached-signature verification")
        else:
            completed = subprocess.run(
                [
                    "gpgv",
                    "--keyring",
                    str(keyring_path),
                    str(signature_path),
                    str(manifest_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "unknown gpgv error"
                errors.append(f"manifest signature verification failed: {detail}")
            else:
                signature_verified = True

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read manifest: {exc}", file=sys.stderr)
        return 2

    if not isinstance(manifest, dict):
        print("error: manifest root must be an object", file=sys.stderr)
        return 2
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if not isinstance(manifest.get("bundle_id"), str) or not manifest["bundle_id"].strip():
        errors.append("bundle_id must be a non-empty string")
    if not isinstance(manifest.get("generated_at"), str) or not manifest["generated_at"].strip():
        errors.append("generated_at must be a non-empty date-time string")

    documents = manifest.get("documents")
    if not isinstance(documents, list):
        errors.append("documents must be an array")
        documents = []

    listed_paths: set[str] = set()
    verified = 0

    for index, document in enumerate(documents):
        prefix = f"documents[{index}]"
        if not isinstance(document, dict):
            errors.append(f"{prefix} must be an object")
            continue

        relative = safe_relative_path(document.get("path"))
        if relative is None:
            errors.append(f"{prefix}.path is unsafe or invalid")
            continue
        relative_text = relative.as_posix()
        if relative_text in listed_paths:
            errors.append(f"duplicate manifest path: {relative_text}")
            continue
        listed_paths.add(relative_text)

        expected_hash = document.get("sha256")
        if not isinstance(expected_hash, str) or not SHA256_RE.fullmatch(expected_hash):
            errors.append(f"{prefix}.sha256 is invalid")
            continue

        for field in ("vendor", "product", "title", "retrieved_at"):
            if not isinstance(document.get(field), str) or not document[field].strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        if document.get("status") not in VALID_STATUS:
            errors.append(f"{prefix}.status is invalid")
        if not valid_https_url(document.get("source_url")):
            errors.append(f"{prefix}.source_url must be an HTTPS URL")

        target = bundle.joinpath(*relative.parts)
        try:
            resolved_target = target.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"missing file: {relative_text}")
            continue
        if bundle not in resolved_target.parents:
            errors.append(f"path escapes bundle: {relative_text}")
            continue
        if target.is_symlink() or not resolved_target.is_file():
            errors.append(f"manifest path is not a regular non-symlink file: {relative_text}")
            continue

        actual_hash = sha256_file(resolved_target)
        if actual_hash.lower() != expected_hash.lower():
            errors.append(
                f"hash mismatch: {relative_text} expected {expected_hash.lower()} got {actual_hash}"
            )
            continue
        verified += 1

    manifest_inside_bundle = None
    try:
        manifest_inside_bundle = manifest_path.relative_to(bundle).as_posix()
    except ValueError:
        pass
    signature_inside_bundle = None
    if signature_path is not None:
        try:
            signature_inside_bundle = signature_path.relative_to(bundle).as_posix()
        except ValueError:
            pass

    unlisted: list[str] = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            errors.append(f"bundle contains symlink: {path.relative_to(bundle).as_posix()}")
            continue
        if not path.is_file():
            continue
        relative_text = path.relative_to(bundle).as_posix()
        if relative_text in {manifest_inside_bundle, signature_inside_bundle}:
            continue
        if relative_text not in listed_paths:
            unlisted.append(relative_text)

    if unlisted:
        message = f"{len(unlisted)} unlisted regular file(s): " + ", ".join(unlisted[:10])
        if len(unlisted) > 10:
            message += ", ..."
        if args.strict_unlisted:
            errors.append(message)
        else:
            warnings.append(message)

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)

    if errors:
        print(f"verification failed: {len(errors)} error(s), {verified} file(s) verified")
        return 1

    print(
        f"verification passed: bundle={manifest.get('bundle_id')} "
        f"documents={len(documents)} verified={verified} "
        f"signature={'verified' if signature_verified else 'explicitly-unsigned'} "
        f"warnings={len(warnings)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
