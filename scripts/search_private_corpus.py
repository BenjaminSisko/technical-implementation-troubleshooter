#!/usr/bin/env python3
"""Search a private troubleshooting SQLite FTS5 index and return citations."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a private troubleshooting corpus index."
    )
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--root", action="append", help="Restrict to a root label.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--raw-fts-query",
        action="store_true",
        help="Treat --query as raw FTS5 syntax instead of a safe all-terms query.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def safe_fts_query(value: str) -> str:
    terms = re.findall(r"[\w][\w.+:/-]*", value, flags=re.UNICODE)
    if not terms:
        raise ValueError("query contains no searchable terms")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def main() -> int:
    args = parse_args()
    index = args.index.expanduser().resolve()
    if not index.is_file():
        print(f"error: index does not exist: {index}", file=sys.stderr)
        return 2
    if args.limit < 1 or args.limit > 100:
        print("error: --limit must be between 1 and 100", file=sys.stderr)
        return 2
    try:
        query = args.query if args.raw_fts_query else safe_fts_query(args.query)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    sql = """
        SELECT
            root_label,
            relative_path,
            CAST(chunk_no AS INTEGER),
            heading,
            snippet(chunks, 5, '[', ']', ' … ', 36),
            content_sha256,
            document_id,
            bm25(chunks, 8.0, 1.0)
        FROM chunks
        WHERE chunks MATCH ?
    """
    parameters: list[object] = [query]
    if args.root:
        placeholders = ",".join("?" for _ in args.root)
        sql += f" AND root_label IN ({placeholders})"
        parameters.extend(args.root)
    sql += " ORDER BY bm25(chunks, 8.0, 1.0), root_label, relative_path, CAST(chunk_no AS INTEGER) LIMIT ?"
    parameters.append(args.limit)

    try:
        connection = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        rows = connection.execute(sql, parameters).fetchall()
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        connection.close()
    except sqlite3.Error as exc:
        print(f"error: search failed: {exc}", file=sys.stderr)
        return 1

    results = []
    for root, path, chunk_no, heading, snippet, chunk_hash, document_id, score in rows:
        results.append(
            {
                "citation": f"{root}:{path}#chunk-{chunk_no}",
                "root": root,
                "relative_path": path,
                "chunk": chunk_no,
                "heading": heading,
                "snippet": snippet,
                "chunk_sha256": chunk_hash,
                "document_id": document_id,
                "score": score,
            }
        )
    if args.json:
        print(
            json.dumps(
                {
                    "bundle_id": metadata.get("bundle_id"),
                    "classification": metadata.get("classification"),
                    "query": args.query,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"bundle={metadata.get('bundle_id', 'unknown')} "
            f"classification={metadata.get('classification', 'unknown')} "
            f"results={len(results)}"
        )
        for number, result in enumerate(results, start=1):
            print(
                f"\n{number}. {result['citation']}\n"
                f"   heading: {result['heading']}\n"
                f"   chunk-sha256: {result['chunk_sha256']}\n"
                f"   {result['snippet']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
