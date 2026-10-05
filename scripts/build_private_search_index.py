#!/usr/bin/env python3
"""Build a private, citation-bearing SQLite FTS5 index from approved text roots."""

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
from pathlib import Path


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
    "credentials",
    "credentials.json",
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
SENSITIVE_PREFIXES = ("id_dsa", "id_ecdsa", "id_ed25519", "id_rsa")
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class VisibleTextParser(HTMLParser):
    """Extract visible HTML text while retaining headings as Markdown-like markers."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.heading_level: int | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if lowered in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = int(lowered[1])
            self.parts.append("\n" + ("#" * self.heading_level) + " ")
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
        if lowered.startswith("h") and len(lowered) == 2 and lowered[1].isdigit():
            self.heading_level = None

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a private full-text SQLite FTS5 index with source citations."
    )
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Approved corpus root; repeat for multiple roots.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output SQLite path.")
    parser.add_argument(
        "--bundle-id",
        default="unreleased-private-corpus",
        help="Immutable bundle identifier recorded in the index metadata.",
    )
    parser.add_argument(
        "--classification",
        choices=("private", "restricted"),
        default="private",
        help="Index classification (default: private).",
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
        help="Also index .log files. Review them for secrets and personal data first.",
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


def is_sensitive(path: Path) -> bool:
    lowered = path.name.lower()
    return (
        lowered in SENSITIVE_EXACT_NAMES
        or lowered.startswith(SENSITIVE_PREFIXES)
        or path.suffix.lower() in SENSITIVE_SUFFIXES
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines()]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if line:
            normalized.append(line)
            blank = False
        elif not blank:
            normalized.append("")
            blank = True
    return "\n".join(normalized).strip()


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
    root: Path, max_file_bytes: int, include_logs: bool, skipped: dict[str, int]
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
            if path.is_symlink():
                skipped["symlink"] += 1
                continue
            if is_sensitive(path):
                skipped["sensitive"] += 1
                continue
            if path.suffix.lower() not in allowed:
                skipped["unsupported"] += 1
                continue
            try:
                stat = path.stat()
            except OSError:
                skipped["unreadable"] += 1
                continue
            if not path.is_file():
                skipped["unsupported"] += 1
                continue
            if stat.st_size > max_file_bytes:
                skipped["large"] += 1
                continue
            yield path, stat


def chunk_text(text: str, max_chars: int) -> list[tuple[str, str]]:
    if not text:
        return []
    chunks: list[tuple[str, str]] = []
    heading = "(document)"
    current_heading = heading
    current: list[str] = []
    current_size = 0

    def flush() -> None:
        nonlocal current, current_size
        content = "\n\n".join(part for part in current if part).strip()
        if content:
            chunks.append((current_heading, content))
        current = []
        current_size = 0

    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
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
                chunks.append((heading, piece))
            start = max(end, start + 1)
    flush()
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
            UNIQUE(root_label, relative_path)
        );
        CREATE VIRTUAL TABLE chunks USING fts5(
            document_id UNINDEXED,
            root_label UNINDEXED,
            relative_path UNINDEXED,
            chunk_no UNINDEXED,
            heading,
            content,
            content_sha256 UNINDEXED,
            tokenize='unicode61'
        );
        """
    )


def main() -> int:
    args = parse_args()
    if args.max_file_bytes <= 0 or args.chunk_chars < 500:
        print("error: size limits must be positive and --chunk-chars at least 500", file=sys.stderr)
        return 2
    try:
        roots = [parse_root(item) for item in args.root]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    labels = [label for label, _ in roots]
    if len(labels) != len(set(labels)):
        print("error: root labels must be unique", file=sys.stderr)
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
        "sensitive": 0,
        "large": 0,
        "unsupported": 0,
        "symlink": 0,
        "unreadable": 0,
        "empty": 0,
    }
    document_count = 0
    chunk_count = 0

    try:
        connection = sqlite3.connect(temporary)
        create_schema(connection)
        metadata = {
            "schema_version": "1",
            "bundle_id": args.bundle_id,
            "classification": args.classification,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "absolute_paths_stored": "false",
            "chunk_chars": str(args.chunk_chars),
        }
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES(?, ?)", sorted(metadata.items())
        )
        for label, root in sorted(roots):
            for path, stat in iter_files(
                root, args.max_file_bytes, args.include_logs, skipped
            ):
                try:
                    raw = path.read_bytes()
                except OSError:
                    skipped["unreadable"] += 1
                    continue
                text = extract_text(path, raw)
                chunks = chunk_text(text, args.chunk_chars)
                if not chunks:
                    skipped["empty"] += 1
                    continue
                relative_path = path.relative_to(root).as_posix()
                digest = sha256_bytes(raw)
                document_id = hashlib.sha256(
                    f"{label}\x00{relative_path}\x00{digest}".encode("utf-8")
                ).hexdigest()
                connection.execute(
                    """
                    INSERT INTO documents(
                        document_id, root_label, relative_path, suffix, size_bytes,
                        modified_at, sha256, chunk_count
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
                for index, (heading, content) in enumerate(chunks, start=1):
                    connection.execute(
                        """
                        INSERT INTO chunks(
                            document_id, root_label, relative_path, chunk_no,
                            heading, content, content_sha256
                        ) VALUES(?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            document_id,
                            label,
                            relative_path,
                            index,
                            heading,
                            content,
                            sha256_bytes(content.encode("utf-8")),
                        ),
                    )
                document_count += 1
                chunk_count += len(chunks)
        if document_count == 0:
            raise RuntimeError("no eligible non-empty documents were indexed")
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES(?, ?)",
            ("skipped", json.dumps(skipped, sort_keys=True)),
        )
        connection.execute("INSERT INTO chunks(chunks) VALUES('optimize')")
        connection.commit()
        connection.execute("VACUUM")
        connection.close()
        temporary.replace(output)
    except Exception as exc:
        try:
            connection.close()
        except Exception:
            pass
        temporary.unlink(missing_ok=True)
        print(f"error: index build failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"indexed documents={document_count} chunks={chunk_count} output={output} "
        f"skipped={sum(skipped.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
