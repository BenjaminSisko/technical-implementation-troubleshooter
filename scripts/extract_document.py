#!/usr/bin/env python3
"""Extract offline-searchable text from PDF and common Office documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


MAX_ARCHIVE_MEMBERS = 20_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract normalized text without executing document content."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def check_archive(archive: zipfile.ZipFile) -> None:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError(f"archive contains too many members: {len(members)}")
    total = sum(member.file_size for member in members)
    if total > MAX_UNCOMPRESSED_BYTES:
        raise ValueError(f"archive expands beyond limit: {total} bytes")
    for member in members:
        mode = (member.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise ValueError(f"archive contains a symbolic link: {member.filename}")


def xml_text(data: bytes, text_suffix: str) -> list[str]:
    root = ElementTree.fromstring(data)
    return [
        node.text or ""
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == text_suffix and node.text
    ]


def extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        check_archive(archive)
        data = archive.read("word/document.xml")
    root = ElementTree.fromstring(data)
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if paragraph.tag.rsplit("}", 1)[-1] != "p":
            continue
        pieces: list[str] = []
        for node in paragraph.iter():
            local = node.tag.rsplit("}", 1)[-1]
            if local == "t" and node.text:
                pieces.append(node.text)
            elif local == "tab":
                pieces.append("\t")
            elif local in {"br", "cr"}:
                pieces.append("\n")
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def numeric_suffix(name: str) -> int:
    match = re.search(r"(\d+)(?=\.xml$)", name)
    return int(match.group(1)) if match else 0


def extract_pptx(path: Path) -> str:
    sections: list[str] = []
    with zipfile.ZipFile(path) as archive:
        check_archive(archive)
        slides = sorted(
            (
                name
                for name in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ),
            key=numeric_suffix,
        )
        for number, name in enumerate(slides, start=1):
            lines = [value.strip() for value in xml_text(archive.read(name), "t")]
            lines = [value for value in lines if value]
            sections.append(f"# Slide {number}\n\n" + "\n".join(lines))
    return "\n\f\n".join(sections)


def extract_xlsx(path: Path) -> str:
    sections: list[str] = []
    with zipfile.ZipFile(path) as archive:
        check_archive(archive)
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root:
                shared.append("".join(xml_text(ElementTree.tostring(item), "t")))
        sheets = sorted(
            (
                name
                for name in archive.namelist()
                if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
            ),
            key=numeric_suffix,
        )
        for number, name in enumerate(sheets, start=1):
            root = ElementTree.fromstring(archive.read(name))
            rows: list[str] = []
            for row in root.iter():
                if row.tag.rsplit("}", 1)[-1] != "row":
                    continue
                cells: list[str] = []
                for cell in row:
                    if cell.tag.rsplit("}", 1)[-1] != "c":
                        continue
                    cell_type = cell.attrib.get("t")
                    if cell_type == "inlineStr":
                        value = "".join(
                            node.text or ""
                            for node in cell.iter()
                            if node.tag.rsplit("}", 1)[-1] == "t"
                        )
                    else:
                        value = next(
                            (
                                node.text or ""
                                for node in cell
                                if node.tag.rsplit("}", 1)[-1] == "v"
                            ),
                            "",
                        )
                    if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                        value = shared[int(value)]
                    cells.append(value.replace("\t", " ").replace("\n", " "))
                if cells:
                    rows.append("\t".join(cells))
            sections.append(f"# Sheet {number}\n\n" + "\n".join(rows))
    return "\n\f\n".join(sections)


def extract_pdf(path: Path) -> str:
    executable = shutil.which("pdftotext")
    if executable is None:
        raise ValueError("pdftotext is required for PDF extraction")
    completed = subprocess.run(
        [executable, "-layout", str(path), "-"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"pdftotext failed: {detail or completed.returncode}")
    return completed.stdout.decode("utf-8", errors="replace")


def normalize(text: str) -> str:
    pages = text.replace("\r\n", "\n").replace("\r", "\n").split("\f")
    normalized_pages = ["\n".join(line.rstrip() for line in page.splitlines()).strip() for page in pages]
    return "\f".join(page for page in normalized_pages if page).strip()


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    receipt = (
        args.receipt.expanduser().resolve()
        if args.receipt
        else output.with_suffix(output.suffix + ".receipt.json")
    )
    if not source.is_file() or source.is_symlink():
        print(f"error: input must be a regular non-symlink file: {source}", file=sys.stderr)
        return 2
    if (output.exists() or receipt.exists()) and not args.force:
        print("error: output or receipt exists; use --force to replace", file=sys.stderr)
        return 2
    suffix = source.suffix.lower()
    try:
        if suffix == ".pdf":
            text, extractor = extract_pdf(source), "pdftotext-layout"
        elif suffix in {".docx", ".docm"}:
            text, extractor = extract_docx(source), "stdlib-docx-xml"
        elif suffix in {".pptx", ".pptm"}:
            text, extractor = extract_pptx(source), "stdlib-pptx-xml"
        elif suffix in {".xlsx", ".xlsm"}:
            text, extractor = extract_xlsx(source), "stdlib-xlsx-xml"
        else:
            text = source.read_text(encoding="utf-8", errors="replace")
            extractor = "utf8-text"
        normalized = normalize(text)
        if not normalized:
            raise ValueError("extractor produced no searchable text")
        source_bytes = source.read_bytes()
        output_bytes = (normalized + "\n").encode("utf-8")
        receipt_payload = {
            "schema_version": 1,
            "source_name": source.name,
            "source_sha256": sha256(source_bytes),
            "source_bytes": len(source_bytes),
            "output_name": output.name,
            "output_sha256": sha256(output_bytes),
            "output_bytes": len(output_bytes),
            "extractor": extractor,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "page_separator": "form-feed",
        }
        atomic_write(output, output_bytes)
        atomic_write(
            receipt,
            (json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        print(f"error: extraction failed: {exc}", file=sys.stderr)
        return 1
    print(f"extracted source={source.name} output={output} receipt={receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
