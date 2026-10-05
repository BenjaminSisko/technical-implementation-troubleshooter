#!/usr/bin/env python3
"""Create an immutable sanitized corpus from hash-pinned reviewed documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional

from sensitive_content import (
    DETECTOR_PATTERNS,
    detect_secret_types,
    redact_approved_content,
)


SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
METADATA_FIELDS = {
    "architecture",
    "classification",
    "document_type",
    "hardware_family",
    "kernel_pattern",
    "os_family",
    "os_major",
    "platform",
    "product",
    "published_at",
    "retrieved_at",
    "source_url",
    "status",
    "superseded_by",
    "title",
    "vendor",
    "version",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Redact only hash-pinned, explicitly reviewed secret-pattern examples "
            "and generate an auditable sanitized corpus."
        )
    )
    parser.add_argument("--root", required=True, type=Path, help="Reviewed source root.")
    parser.add_argument(
        "--approval-manifest",
        required=True,
        type=Path,
        help="Private JSON manifest listing approved paths, hashes, and detectors.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New immutable sanitized document root.",
    )
    parser.add_argument(
        "--report", required=True, type=Path, help="Private sanitization receipt JSON."
    )
    parser.add_argument(
        "--document-manifest",
        required=True,
        type=Path,
        help="Generated index-compatible metadata manifest for sanitized documents.",
    )
    parser.add_argument(
        "--bundle-id", required=True, help="Immutable identifier for the sanitized set."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sources and redactions without writing outputs.",
    )
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_relative_path(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{field} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe {field}: {value!r}")
    return path.as_posix()


def load_approval_manifest(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read approval manifest {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"approval manifest must use schema_version {SCHEMA_VERSION}")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("approval manifest documents must be a non-empty array")
    normalized: list[dict[str, object]] = []
    seen_sources: set[str] = set()
    seen_outputs: set[str] = set()
    for number, raw_document in enumerate(documents, start=1):
        if not isinstance(raw_document, dict):
            raise ValueError(f"document {number} must be an object")
        source_path = safe_relative_path(raw_document.get("path"), "path")
        output_path = safe_relative_path(
            raw_document.get("output_path", source_path), "output_path"
        )
        digest = raw_document.get("sha256")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ValueError(f"document {number} requires a lowercase SHA-256 digest")
        approved = raw_document.get("approved_detectors")
        if not isinstance(approved, list) or not approved:
            raise ValueError(f"document {number} requires approved_detectors")
        if not all(isinstance(item, str) for item in approved):
            raise ValueError(f"document {number} detector names must be strings")
        detectors = sorted(set(approved))
        unknown = set(detectors) - set(DETECTOR_PATTERNS)
        if unknown:
            raise ValueError(
                f"document {number} has unknown detectors: {', '.join(sorted(unknown))}"
            )
        metadata = raw_document.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"document {number} metadata must be an object")
        unsupported = set(metadata) - METADATA_FIELDS
        if unsupported:
            raise ValueError(
                f"document {number} has unsupported metadata fields: "
                f"{', '.join(sorted(unsupported))}"
            )
        if not all(isinstance(value, str) for value in metadata.values()):
            raise ValueError(f"document {number} metadata values must be strings")
        if source_path in seen_sources:
            raise ValueError(f"duplicate source path: {source_path}")
        if output_path in seen_outputs:
            raise ValueError(f"duplicate output path: {output_path}")
        seen_sources.add(source_path)
        seen_outputs.add(output_path)
        normalized.append(
            {
                "path": source_path,
                "output_path": output_path,
                "sha256": digest.lower(),
                "approved_detectors": detectors,
                "metadata": metadata,
            }
        )
    return normalized


def resolved_child(root: Path, relative: str) -> Path:
    lexical = root / PurePosixPath(relative)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"path contains a symbolic link: {relative}")
    candidate = lexical.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes the reviewed root: {relative}") from exc
    return candidate


def write_private_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def existing_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def main() -> int:
    args = parse_args()
    try:
        source_root = args.root.expanduser().resolve(strict=True)
        approval_manifest = args.approval_manifest.expanduser().resolve(strict=True)
        output = args.output.expanduser().resolve()
        report_path = args.report.expanduser().resolve()
        document_manifest_path = args.document_manifest.expanduser().resolve()
        if not source_root.is_dir():
            raise ValueError(f"reviewed root is not a directory: {source_root}")
        if path_is_within(output, source_root):
            raise ValueError("sanitized output must not be inside the reviewed source root")
        if report_path == document_manifest_path:
            raise ValueError("report and document-manifest paths must be different")
        for label, private_output in (
            ("report", report_path),
            ("document manifest", document_manifest_path),
        ):
            if path_is_within(private_output, source_root):
                raise ValueError(f"{label} must not be written inside the source root")
            if path_is_within(private_output, output):
                raise ValueError(f"{label} must not be written inside the sanitized root")
        documents = load_approval_manifest(approval_manifest)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output_exists = output.is_dir()
    if output.exists() and not output_exists:
        print(f"error: output exists and is not a directory: {output}", file=sys.stderr)
        return 2
    expected_outputs = {str(item["output_path"]) for item in documents}
    if output_exists:
        if any(path.is_symlink() for path in output.rglob("*")):
            print(
                "error: existing immutable output contains a symbolic link",
                file=sys.stderr,
            )
            return 1
        found_outputs = existing_files(output)
        if found_outputs != expected_outputs:
            print(
                "error: existing immutable output has missing or unlisted files; "
                "use a new bundle identifier and output directory",
                file=sys.stderr,
            )
            return 1

    stage: Optional[Path] = None
    records: list[dict[str, object]] = []
    index_documents: list[dict[str, object]] = []
    try:
        if not args.dry_run and not output_exists:
            output.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(
                tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent)
            )
            os.chmod(stage, 0o700)
        for document in documents:
            source_relative = str(document["path"])
            output_relative = str(document["output_path"])
            source = resolved_child(source_root, source_relative)
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f"reviewed source is missing or unsafe: {source_relative}")
            raw = source.read_bytes()
            source_sha256 = sha256_bytes(raw)
            if source_sha256 != document["sha256"]:
                raise RuntimeError(f"source hash mismatch: {source_relative}")
            actual_detectors = detect_secret_types(raw)
            approved_detectors = list(document["approved_detectors"])
            if actual_detectors != approved_detectors:
                raise RuntimeError(
                    f"detector mismatch for {source_relative}: "
                    f"approved={approved_detectors} actual={actual_detectors}"
                )
            sanitized, counts = redact_approved_content(raw, set(approved_detectors))
            missing_replacements = [name for name, count in counts.items() if count < 1]
            if missing_replacements:
                raise RuntimeError(
                    f"approved content could not be safely redacted for {source_relative}: "
                    f"{', '.join(missing_replacements)}"
                )
            remaining = detect_secret_types(sanitized)
            if remaining:
                raise RuntimeError(
                    f"sanitized content still triggers detectors for {source_relative}: "
                    f"{', '.join(remaining)}"
                )
            sanitized_sha256 = sha256_bytes(sanitized)
            if output_exists:
                existing = resolved_child(output, output_relative)
                if not existing.is_file() or existing.is_symlink():
                    raise RuntimeError(f"existing sanitized output is unsafe: {output_relative}")
                if sha256_bytes(existing.read_bytes()) != sanitized_sha256:
                    raise RuntimeError(
                        f"existing immutable output hash mismatch: {output_relative}"
                    )
            elif stage is not None:
                write_private_bytes(stage / PurePosixPath(output_relative), sanitized)
            record = {
                "source_path": source_relative,
                "source_sha256": source_sha256,
                "sanitized_path": output_relative,
                "sanitized_sha256": sanitized_sha256,
                "approved_detectors": approved_detectors,
                "replacement_counts": counts,
            }
            records.append(record)
            index_record: dict[str, object] = {
                "path": output_relative,
                "sha256": sanitized_sha256,
                "source_sha256": source_sha256,
                "sanitization_detectors": approved_detectors,
            }
            index_record.update(document["metadata"])
            index_documents.append(index_record)
        if args.dry_run:
            print(
                f"dry-run: validated documents={len(records)} "
                f"detectors={sum(len(item['approved_detectors']) for item in records)} "
                "outputs_written=0"
            )
            return 0
        if stage is not None:
            stage.replace(output)
            stage = None
        generated_at = datetime.now(timezone.utc).isoformat()
        report = {
            "schema_version": SCHEMA_VERSION,
            "bundle_id": args.bundle_id,
            "generated_at": generated_at,
            "source_root_stored": False,
            "document_count": len(records),
            "documents": records,
        }
        index_manifest = {
            "schema_version": 1,
            "bundle_id": args.bundle_id,
            "generated_at": generated_at,
            "documents": index_documents,
        }
        atomic_json(report_path, report)
        atomic_json(document_manifest_path, index_manifest)
    except (OSError, RuntimeError, ValueError) as exc:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        print(f"error: sanitization failed: {exc}", file=sys.stderr)
        return 1

    mode = "verified-existing" if output_exists else "created"
    print(
        f"sanitized documents={len(records)} output={output} mode={mode} "
        f"report={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
