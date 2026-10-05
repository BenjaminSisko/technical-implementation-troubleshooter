#!/usr/bin/env python3
"""Acquire approved anonymous public-web sources into a private content-addressed cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


CONTENT_EXTENSIONS = {
    "application/json": ".json",
    "application/pdf": ".pdf",
    "application/xml": ".xml",
    "application/xhtml+xml": ".xhtml",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/markdown": ".md",
    "text/plain": ".txt",
    "text/xml": ".xml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download selected anonymous public-web registry sources into a private, "
            "content-addressed raw cache."
        )
    )
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--source-id",
        action="append",
        required=True,
        help="Source ID to acquire; repeat for multiple sources.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=50 * 1024 * 1024,
        help="Maximum response bytes per source (default: 50 MiB).",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def load_sources(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("registry sources must be an array")
    result: dict[str, dict] = {}
    for item in sources:
        if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
            raise ValueError("registry contains an invalid source record")
        if item["source_id"] in result:
            raise ValueError(f"duplicate source_id: {item['source_id']}")
        result[item["source_id"]] = item
    return result


def extension_for(content_type: str, final_url: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type in CONTENT_EXTENSIONS:
        return CONTENT_EXTENSIONS[media_type]
    suffix = Path(urlparse(final_url).path).suffix.lower()
    if suffix and len(suffix) <= 10 and suffix.replace(".", "").isalnum():
        return suffix
    return ".bin"


def acquire(source: dict, output: Path, timeout: int, max_bytes: int) -> tuple[str, Path]:
    request = Request(
        source["canonical_url"],
        headers={
            "User-Agent": (
                "technical-implementation-troubleshooter/1 "
                "(private vendor-corpus acquisition)"
            ),
            "Accept": "*/*",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme != "https":
            raise ValueError(f"final URL is not HTTPS: {final_url}")
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > max_bytes:
            raise ValueError(
                f"declared response size {declared} exceeds limit {max_bytes}"
            )
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError(f"response exceeds limit {max_bytes}")
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        last_modified = response.headers.get("Last-Modified")
        etag = response.headers.get("ETag")

    digest = hashlib.sha256(body).hexdigest()
    version_dir = output / source["source_id"] / digest[:16]
    extension = extension_for(content_type, final_url)
    source_path = version_dir / f"source{extension}"
    receipt_path = version_dir / "receipt.json"
    if source_path.exists() and receipt_path.exists():
        if hashlib.sha256(source_path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"existing content-addressed file is corrupt: {source_path}")
        return "existing", version_dir

    receipt = {
        "schema_version": 1,
        "source_id": source["source_id"],
        "vendor": source["vendor"],
        "product": source["product"],
        "title": source["title"],
        "canonical_url": source["canonical_url"],
        "final_url": final_url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_type": content_type,
        "byte_size": len(body),
        "sha256": digest,
        "etag": etag,
        "last_modified": last_modified,
        "access_class": source["access_class"],
        "redistribution_class": source["redistribution_class"],
        "classification": source["default_classification"],
        "acquisition_mode": source["acquisition_mode"],
        "relative_source_path": source_path.name,
        "status": "candidate",
    }
    atomic_write(source_path, body)
    atomic_write(
        receipt_path,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return "acquired", version_dir


def main() -> int:
    args = parse_args()
    if args.timeout <= 0 or args.max_bytes <= 0:
        print("error: timeout and max-bytes must be positive", file=sys.stderr)
        return 2
    try:
        sources = load_sources(args.registry.expanduser().resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: cannot load registry: {exc}", file=sys.stderr)
        return 2

    missing = sorted(set(args.source_id) - set(sources))
    if missing:
        print(f"error: unknown source IDs: {', '.join(missing)}", file=sys.stderr)
        return 2
    selected = [sources[source_id] for source_id in dict.fromkeys(args.source_id)]
    errors: list[str] = []
    for source in selected:
        if source.get("access_class") != "public-anonymous":
            errors.append(
                f"{source['source_id']}: access_class is {source.get('access_class')}; "
                "use an authorized manual acquisition"
            )
        if source.get("acquisition_mode") != "public-web":
            errors.append(
                f"{source['source_id']}: acquisition_mode is "
                f"{source.get('acquisition_mode')}; this collector only handles public-web"
            )
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 2

    output = args.output.expanduser().resolve()
    for source in selected:
        if args.dry_run:
            print(
                f"would acquire {source['source_id']} from {source['canonical_url']} "
                f"into {output}"
            )
            continue
        try:
            state, version_dir = acquire(
                source, output, timeout=args.timeout, max_bytes=args.max_bytes
            )
        except (HTTPError, URLError, OSError, ValueError) as exc:
            print(f"error: {source['source_id']}: {exc}", file=sys.stderr)
            errors.append(source["source_id"])
            continue
        print(f"{state}: {source['source_id']} -> {version_dir}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
