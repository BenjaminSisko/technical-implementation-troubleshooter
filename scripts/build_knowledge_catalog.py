#!/usr/bin/env python3
"""Build a metadata-only catalog for approved troubleshooting knowledge roots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_SUFFIXES = {
    ".adoc",
    ".cfg",
    ".conf",
    ".ini",
    ".json",
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
    "secrets",
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

SENSITIVE_PREFIXES = (
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
)

LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
MARKDOWN_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
KEY_TITLE_RE = re.compile(r"^(?:name|title):\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Catalog approved documentation and configuration without embedding file contents."
    )
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Knowledge root with a stable label; repeat for multiple roots.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output JSON path.")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=5 * 1024 * 1024,
        help="Skip individual files larger than this size (default: 5 MiB).",
    )
    parser.add_argument(
        "--include-root-paths",
        action="store_true",
        help="Include absolute root paths. Omit for a portable, non-disclosing catalog.",
    )
    return parser.parse_args()


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"root must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid root label: {label!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"knowledge root is not a directory: {path}")
    return label, path


def is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    if name in SENSITIVE_EXACT_NAMES:
        return True
    if name.startswith(SENSITIVE_PREFIXES):
        return True
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_title(path: Path) -> str:
    fallback = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            sample = handle.read(64 * 1024)
    except OSError:
        return fallback

    if path.suffix.lower() == ".md":
        match = MARKDOWN_TITLE_RE.search(sample)
        if match:
            return match.group(1).strip()[:240]

    if path.suffix.lower() in {".yaml", ".yml", ".toml"}:
        match = KEY_TITLE_RE.search(sample)
        if match:
            return match.group(1).strip()[:240]

    if path.suffix.lower() == ".json":
        try:
            value = json.loads(sample)
            if isinstance(value, dict):
                title = value.get("title") or value.get("name")
                if isinstance(title, str) and title.strip():
                    return title.strip()[:240]
        except json.JSONDecodeError:
            pass

    return fallback[:240]


def iter_catalog_files(root: Path, max_bytes: int, skipped: dict[str, int]):
    for current, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name
            for name in directories
            if name not in EXCLUDED_DIRECTORIES and not (Path(current) / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = Path(current) / filename
            if path.is_symlink():
                skipped["symlink"] += 1
                continue
            if is_sensitive(path):
                skipped["sensitive"] += 1
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                skipped["unsupported"] += 1
                continue
            try:
                stat = path.stat()
            except OSError:
                skipped["unsupported"] += 1
                continue
            if not path.is_file():
                skipped["unsupported"] += 1
                continue
            if stat.st_size > max_bytes:
                skipped["large"] += 1
                continue
            yield path, stat


def atomic_write_json(output: Path, payload: dict) -> None:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, prefix=f".{output.name}.", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def main() -> int:
    args = parse_args()
    if args.max_bytes <= 0:
        print("error: --max-bytes must be positive", file=sys.stderr)
        return 2

    try:
        roots = [parse_root(value) for value in args.root]
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    labels = [label for label, _ in roots]
    if len(labels) != len(set(labels)):
        print("error: root labels must be unique", file=sys.stderr)
        return 2

    items: list[dict] = []
    skipped_totals = {"sensitive": 0, "large": 0, "unsupported": 0, "symlink": 0}

    for label, root in sorted(roots):
        root_skipped = {"sensitive": 0, "large": 0, "unsupported": 0, "symlink": 0}
        for path, stat in iter_catalog_files(root, args.max_bytes, root_skipped):
            items.append(
                {
                    "root": label,
                    "relative_path": path.relative_to(root).as_posix(),
                    "title": extract_title(path),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "sha256": sha256_file(path),
                }
            )
        for key, count in root_skipped.items():
            skipped_totals[key] += count

    items.sort(key=lambda item: (item["root"], item["relative_path"].lower()))
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "roots": [
            {
                "label": label,
                **({"path": str(path)} if args.include_root_paths else {}),
            }
            for label, path in sorted(roots)
        ],
        "file_count": len(items),
        "skipped": skipped_totals,
        "files": items,
    }
    atomic_write_json(args.output, payload)
    print(
        f"cataloged {len(items)} files into {args.output}; "
        f"skipped {sum(skipped_totals.values())} files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
