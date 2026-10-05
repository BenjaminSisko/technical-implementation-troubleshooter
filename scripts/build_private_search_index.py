#!/usr/bin/env python3
"""Build a private, metadata-aware SQLite FTS5 index from approved text roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Optional


INDEX_SCHEMA_VERSION = 2
TEXT_SUFFIXES = {
    ".adoc",
    ".cfg",
    ".conf",
    ".csv",
    ".htm",
    ".html",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".ps1",
    ".py",
    ".rst",
    ".sh",
    ".text",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRECTORIES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".terraform",
    ".venv",
    ".vscode",
    "__pycache__",
    "node_modules",
}
SENSITIVE_EXACT_NAMES = {
    ".env",
    ".env.local",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "ansible-vault-password",
    "credentials",
    "credentials.json",
    "kubeconfig",
    "license.dat",
    "secrets.json",
    "vault-password",
    "vault-password.txt",
    "vault_pass",
    "vault_pass.txt",
}
SENSITIVE_SUFFIXES = {
    ".der",
    ".jks",
    ".key",
    ".kdbx",
    ".p12",
    ".pem",
    ".pfx",
    ".pkcs12",
}
SENSITIVE_PREFIXES = (
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secrets.",
)
HIGH_CONFIDENCE_SECRET_PATTERNS = (
    re.compile(
        rb"-----BEGIN (?:(?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----"
    ),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(rb"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~-]{24,}\b"),
)
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
VALID_SOURCE_STATUS = {"candidate", "active", "superseded", "unreviewed"}


class VisibleTextParser(HTMLParser):
    """Extract visible HTML text while retaining headings."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n" + ("#" * int(lowered[1])) + " ")
        elif lowered in {
            "br",
            "p",
            "div",
            "li",
            "tr",
            "section",
            "article",
            "pre",
            "table",
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if lowered in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "div",
            "li",
            "tr",
            "section",
            "article",
            "pre",
            "table",
        }:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a private full-text SQLite FTS5 index with citations."
    )
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Approved corpus root; repeat for multiple roots.",
    )
    parser.add_argument(
        "--document-manifest",
        action="append",
        metavar="LABEL=PATH",
        help=(
            "Vendor-manifest JSON whose paths are relative to LABEL; repeat for "
            "multiple roots or manifests."
        ),
    )
    parser.add_argument("--output", required=True, type=Path, help="Output SQLite path.")
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional private JSON ingestion report with skip reasons and counts.",
    )
    parser.add_argument(
        "--bundle-id",
        default="unreleased-private-corpus",
        help="Immutable bundle identifier recorded in index metadata.",
    )
    parser.add_argument(
        "--classification",
        choices=("public", "private", "restricted"),
        default="private",
        help="Default document classification.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=int,
        default=25 * 1024 * 1024,
        help="Maximum source file size (default: 25 MiB).",
    )
    parser.add_argument(
        "--chunk-chars",
        type=int,
        default=6000,
        help="Approximate maximum characters per chunk (default: 6000).",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Also index .log files after reviewing them for sensitive data.",
    )
    parser.add_argument(
        "--allow-sensitive-content",
        action="store_true",
        help="Index files containing high-confidence secret patterns after review.",
    )
    return parser.parse_args()


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"root must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid root label: {label!r}")
    root = Path(raw_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    return label, root


def safe_manifest_path(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def parse_manifest_spec(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"document manifest must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid document-manifest root label: {label!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"document manifest is not a file: {path}")
    return label, path


def load_document_metadata(
    specs: Optional[list[str]], known_labels: set[str]
) -> tuple[dict[tuple[str, str], dict[str, object]], list[str]]:
    records: dict[tuple[str, str], dict[str, object]] = {}
    manifests: list[str] = []
    for spec in specs or []:
        label, manifest_path = parse_manifest_spec(spec)
        if label not in known_labels:
            raise ValueError(f"document manifest uses unknown root label: {label}")
        manifests.append(f"{label}:{manifest_path.name}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read document manifest {manifest_path}: {exc}") from exc
        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            raise ValueError(f"manifest documents must be an array: {manifest_path}")
        for number, document in enumerate(documents):
            if not isinstance(document, dict):
                raise ValueError(f"manifest document {number} is not an object")
            relative_path = safe_manifest_path(document.get("path"))
            if relative_path is None:
                raise ValueError(f"manifest document {number} has an unsafe path")
            key = (label, relative_path)
            if key in records:
                raise ValueError(f"duplicate metadata for {label}:{relative_path}")
            records[key] = document
    return records, manifests


def is_sensitive_name(path: Path) -> bool:
    lowered = path.name.lower()
    return (
        lowered in SENSITIVE_EXACT_NAMES
        or lowered.startswith(SENSITIVE_PREFIXES)
        or lowered.startswith(".env.")
        or path.suffix.lower() in SENSITIVE_SUFFIXES
    )


def has_high_confidence_secret(raw: bytes) -> bool:
    return any(pattern.search(raw) for pattern in HIGH_CONFIDENCE_SECRET_PATTERNS)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    pages = text.split("\f")
    normalized_pages: list[str] = []
    for page in pages:
        lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in page.splitlines()]
        normalized: list[str] = []
        blank = False
        for line in lines:
            if line:
                normalized.append(line)
                blank = False
            elif not blank:
                normalized.append("")
                blank = True
        normalized_pages.append("\n".join(normalized).strip())
    return "\f".join(normalized_pages).strip("\f")


def extract_text(path: Path, raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        parser = VisibleTextParser()
        parser.feed(text)
        return normalize_text(parser.text())
    if suffix == ".json":
        try:
            return normalize_text(
                json.dumps(json.loads(text), ensure_ascii=False, indent=2, sort_keys=True)
            )
        except json.JSONDecodeError:
            return normalize_text(text)
    return normalize_text(text)


def iter_files(
    label: str,
    root: Path,
    max_file_bytes: int,
    include_logs: bool,
    allow_sensitive_content: bool,
    skipped: dict[str, int],
    skip_examples: list[dict[str, str]],
):
    allowed = set(TEXT_SUFFIXES)
    if include_logs:
        allowed.add(".log")
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if name not in EXCLUDED_DIRECTORIES
            and not (current_path / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = current_path / filename
            reason: Optional[str] = None
            if path.is_symlink():
                reason = "symlink"
            elif is_sensitive_name(path):
                reason = "sensitive_name"
            elif path.suffix.lower() not in allowed:
                reason = "unsupported"
            else:
                try:
                    stat = path.stat()
                except OSError:
                    reason = "unreadable"
                else:
                    if not path.is_file():
                        reason = "unsupported"
                    elif stat.st_size > max_file_bytes:
                        reason = "large"
                    else:
                        try:
                            raw = path.read_bytes()
                        except OSError:
                            reason = "unreadable"
                        else:
                            if not allow_sensitive_content and has_high_confidence_secret(raw):
                                reason = "sensitive_content"
                            else:
                                yield path, stat, raw
                                continue
            skipped[reason] += 1
            if sum(1 for item in skip_examples if item["reason"] == reason) < 20:
                skip_examples.append(
                    {
                        "root_label": label,
                        "path": path.relative_to(root).as_posix(),
                        "reason": reason,
                    }
                )


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")[:100]


def chunk_page(
    text: str, max_chars: int, page_number: Optional[int]
) -> list[tuple[str, str, str]]:
    chunks: list[tuple[str, str, str]] = []
    heading = "(document)"
    current_heading = heading
    current: list[str] = []
    current_size = 0

    def locator() -> str:
        if page_number is not None:
            return f"page-{page_number}"
        heading_slug = slug(current_heading)
        return f"heading-{heading_slug}" if heading_slug else "document"

    def flush() -> None:
        nonlocal current, current_size
        content = "\n\n".join(part for part in current if part).strip()
        if content:
            chunks.append((current_heading, locator(), content))
        current = []
        current_size = 0

    for block in re.split(r"\n\s*\n", text):
        stripped = block.strip()
        if not stripped:
            continue
        first_line = stripped.splitlines()[0]
        match = HEADING_RE.match(first_line)
        if match:
            flush()
            heading = match.group(2).strip()[:300]
            current_heading = heading
        if len(stripped) <= max_chars:
            additional = len(stripped) + (2 if current else 0)
            if current and current_size + additional > max_chars:
                flush()
                current_heading = heading
            current.append(stripped)
            current_size += additional
            continue
        flush()
        current_heading = heading
        start = 0
        while start < len(stripped):
            end = min(start + max_chars, len(stripped))
            if end < len(stripped):
                boundary = stripped.rfind("\n", start, end)
                if boundary <= start:
                    boundary = stripped.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            piece = stripped[start:end].strip()
            if piece:
                chunks.append((heading, locator(), piece))
            start = max(end, start + 1)
    flush()
    return chunks


def chunk_text(text: str, max_chars: int) -> list[tuple[str, str, str]]:
    if not text:
        return []
    pages = text.split("\f")
    page_aware = len(pages) > 1
    chunks: list[tuple[str, str, str]] = []
    for number, page in enumerate(pages, start=1):
        chunks.extend(chunk_page(page, max_chars, number if page_aware else None))
    return chunks


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=FULL;
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            root_label TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            suffix TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            modified_at TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            chunk_count INTEGER NOT NULL,
            vendor TEXT,
            product TEXT,
            title TEXT,
            document_type TEXT,
            version TEXT,
            platform TEXT,
            os_family TEXT,
            os_major TEXT,
            architecture TEXT,
            kernel_pattern TEXT,
            hardware_family TEXT,
            source_url TEXT,
            published_at TEXT,
            retrieved_at TEXT,
            source_status TEXT NOT NULL,
            classification TEXT NOT NULL,
            superseded_by TEXT,
            UNIQUE(root_label, relative_path)
        );
        CREATE INDEX documents_filters ON documents(
            root_label, vendor, product, version, platform,
            source_status, classification, retrieved_at
        );
        CREATE VIRTUAL TABLE chunks USING fts5(
            document_id UNINDEXED,
            root_label UNINDEXED,
            relative_path UNINDEXED,
            chunk_no UNINDEXED,
            source_locator UNINDEXED,
            heading,
            content,
            content_sha256 UNINDEXED,
            tokenize='unicode61'
        );
        """
    )


def metadata_value(document: dict[str, object], name: str) -> Optional[str]:
    value = document.get(name)
    return value if isinstance(value, str) and value.strip() else None


def adjacent_receipt_metadata(path: Path, digest: str) -> dict[str, object]:
    receipt_path = path.parent / "receipt.json"
    if path.name == "receipt.json" or not receipt_path.is_file():
        return {}
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read adjacent receipt for {path.name}: {exc}") from exc
    if not isinstance(receipt, dict):
        raise RuntimeError(f"adjacent receipt is not an object: {receipt_path}")
    if receipt.get("relative_source_path") != path.name:
        return {}
    receipt_hash = metadata_value(receipt, "sha256")
    if receipt_hash and receipt_hash.lower() != digest:
        raise RuntimeError(f"adjacent receipt hash mismatch for {path.name}")
    return {
        "sha256": receipt_hash,
        "vendor": metadata_value(receipt, "vendor"),
        "product": metadata_value(receipt, "product"),
        "title": metadata_value(receipt, "title"),
        "document_type": metadata_value(receipt, "content_type"),
        "version": metadata_value(receipt, "version"),
        "platform": metadata_value(receipt, "platform"),
        "source_url": metadata_value(receipt, "canonical_url")
        or metadata_value(receipt, "final_url"),
        "published_at": metadata_value(receipt, "last_modified"),
        "retrieved_at": metadata_value(receipt, "retrieved_at"),
        "status": metadata_value(receipt, "status") or "candidate",
        "classification": metadata_value(receipt, "classification"),
    }


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path = path.expanduser().resolve()
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


def main() -> int:
    args = parse_args()
    if args.max_file_bytes <= 0 or args.chunk_chars < 500:
        print("error: size limits must be positive and --chunk-chars at least 500", file=sys.stderr)
        return 2
    try:
        roots = [parse_root(item) for item in args.root]
        labels = [label for label, _ in roots]
        if len(labels) != len(set(labels)):
            raise ValueError("root labels must be unique")
        document_metadata, manifests = load_document_metadata(
            args.document_manifest, set(labels)
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    skipped = {
        "sensitive_name": 0,
        "sensitive_content": 0,
        "large": 0,
        "unsupported": 0,
        "symlink": 0,
        "unreadable": 0,
        "empty": 0,
    }
    skip_examples: list[dict[str, str]] = []
    document_count = 0
    chunk_count = 0
    document_count_by_root = {label: 0 for label in labels}
    matched_metadata: set[tuple[str, str]] = set()
    connection: Optional[sqlite3.Connection] = None

    try:
        connection = sqlite3.connect(temporary)
        create_schema(connection)
        index_metadata = {
            "schema_version": str(INDEX_SCHEMA_VERSION),
            "bundle_id": args.bundle_id,
            "classification": args.classification,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "absolute_paths_stored": "false",
            "chunk_chars": str(args.chunk_chars),
            "root_labels": json.dumps(sorted(labels)),
            "document_manifests": json.dumps(manifests),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            sorted(index_metadata.items()),
        )
        for label, root in sorted(roots):
            for path, stat, raw in iter_files(
                label,
                root,
                args.max_file_bytes,
                args.include_logs,
                args.allow_sensitive_content,
                skipped,
                skip_examples,
            ):
                text = extract_text(path, raw)
                chunks = chunk_text(text, args.chunk_chars)
                relative_path = path.relative_to(root).as_posix()
                if not chunks:
                    skipped["empty"] += 1
                    if sum(1 for item in skip_examples if item["reason"] == "empty") < 20:
                        skip_examples.append(
                            {
                                "root_label": label,
                                "path": relative_path,
                                "reason": "empty",
                            }
                        )
                    continue
                digest = sha256_bytes(raw)
                metadata_key = (label, relative_path)
                document = adjacent_receipt_metadata(path, digest)
                document.update(document_metadata.get(metadata_key, {}))
                expected_hash = metadata_value(document, "sha256")
                if expected_hash and expected_hash.lower() != digest:
                    raise RuntimeError(
                        f"manifest hash mismatch for {label}:{relative_path}"
                    )
                if document:
                    matched_metadata.add(metadata_key)
                source_status = metadata_value(document, "status") or "unreviewed"
                if source_status not in VALID_SOURCE_STATUS:
                    raise RuntimeError(
                        f"invalid source status for {label}:{relative_path}: {source_status}"
                    )
                classification = (
                    metadata_value(document, "classification") or args.classification
                )
                document_id = hashlib.sha256(
                    f"{label}\x00{relative_path}\x00{digest}".encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO documents(
                        document_id, root_label, relative_path, suffix, size_bytes,
                        modified_at, sha256, chunk_count, vendor, product, title,
                        document_type, version, platform, os_family, os_major,
                        architecture, kernel_pattern, hardware_family, source_url,
                        published_at, retrieved_at, source_status, classification,
                        superseded_by
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        label,
                        relative_path,
                        path.suffix.lower(),
                        stat.st_size,
                        datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        digest,
                        len(chunks),
                        metadata_value(document, "vendor"),
                        metadata_value(document, "product"),
                        metadata_value(document, "title"),
                        metadata_value(document, "document_type"),
                        metadata_value(document, "version"),
                        metadata_value(document, "platform"),
                        metadata_value(document, "os_family"),
                        metadata_value(document, "os_major"),
                        metadata_value(document, "architecture"),
                        metadata_value(document, "kernel_pattern"),
                        metadata_value(document, "hardware_family"),
                        metadata_value(document, "source_url"),
                        metadata_value(document, "published_at"),
                        metadata_value(document, "retrieved_at"),
                        source_status,
                        classification,
                        metadata_value(document, "superseded_by"),
                    ),
                )
                for index, (heading, locator, content) in enumerate(chunks, start=1):
                    connection.execute(
                        """
                        INSERT INTO chunks(
                            document_id, root_label, relative_path, chunk_no,
                            source_locator, heading, content, content_sha256
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            document_id,
                            label,
                            relative_path,
                            index,
                            locator,
                            heading,
                            content,
                            sha256_bytes(content.encode("utf-8")),
                        ),
                    )
                document_count += 1
                document_count_by_root[label] += 1
                chunk_count += len(chunks)
        if document_count == 0:
            raise RuntimeError("no eligible non-empty documents were indexed")
        unmatched_metadata = sorted(
            f"{label}:{path}" for label, path in set(document_metadata) - matched_metadata
        )
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            ("skipped", json.dumps(skipped, sort_keys=True)),
        )
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            ("unmatched_manifest_documents", json.dumps(unmatched_metadata)),
        )
        connection.execute("INSERT INTO chunks(chunks) VALUES('optimize')")
        connection.commit()
        connection.execute("VACUUM")
        connection.close()
        connection = None
        os.chmod(temporary, 0o600)
        temporary.replace(output)
        report = {
            "schema_version": 1,
            "bundle_id": args.bundle_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "document_count": document_count,
            "document_count_by_root": document_count_by_root,
            "chunk_count": chunk_count,
            "skipped": skipped,
            "skip_examples": skip_examples,
            "unmatched_manifest_documents": unmatched_metadata,
            "absolute_paths_stored": False,
        }
        if args.report:
            atomic_json(args.report, report)
    except Exception as exc:
        if connection is not None:
            connection.close()
        temporary.unlink(missing_ok=True)
        print(f"error: index build failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"indexed documents={document_count} chunks={chunk_count} output={output} "
        f"skipped={sum(skipped.values())} schema={INDEX_SCHEMA_VERSION}"
    )
    if unmatched_metadata:
        print(
            f"warning: unmatched manifest documents={len(unmatched_metadata)}; see report",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
