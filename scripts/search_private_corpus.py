#!/usr/bin/env python3
"""Search a private troubleshooting SQLite FTS5 index and return citations."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional


FILTER_ARGUMENTS = {
    "vendor": "vendor",
    "product": "product",
    "version": "version",
    "platform": "platform",
    "os_family": "os-family",
    "os_major": "os-major",
    "architecture": "architecture",
    "hardware_family": "hardware-family",
    "source_status": "status",
    "classification": "classification",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a private troubleshooting corpus index."
    )
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--root", action="append", help="Restrict to a root label.")
    parser.add_argument("--vendor")
    parser.add_argument("--product")
    parser.add_argument("--version")
    parser.add_argument("--platform")
    parser.add_argument("--os-family")
    parser.add_argument("--os-major")
    parser.add_argument("--architecture")
    parser.add_argument("--hardware-family")
    parser.add_argument(
        "--status",
        dest="source_status",
        choices=("candidate", "active", "superseded", "unreviewed"),
    )
    parser.add_argument(
        "--classification", choices=("public", "private", "restricted")
    )
    parser.add_argument("--retrieved-after", help="ISO-8601 lower retrieval-date bound.")
    parser.add_argument("--retrieved-before", help="ISO-8601 upper retrieval-date bound.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--raw-fts-query",
        action="store_true",
        help="Treat --query as raw FTS5 syntax instead of escaped terms.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Do not retry an all-terms miss using any-term ranking.",
    )
    parser.add_argument(
        "--include-duplicates",
        action="store_true",
        help="Return duplicate chunks from byte-identical source documents.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    return parser.parse_args()


def query_terms(value: str) -> list[str]:
    terms = re.findall(r"[\w][\w.+:/-]*", value, flags=re.UNICODE)
    if not terms:
        raise ValueError("query contains no searchable terms")
    return terms


def quote_term(term: str) -> str:
    return f'"{term.replace(chr(34), chr(34) * 2)}"'


def safe_fts_query(value: str, strategy: str) -> str:
    terms = query_terms(value)
    operator = " AND " if strategy == "all-terms" else " OR "
    return operator.join(quote_term(term) for term in terms)


def index_schema(connection: sqlite3.Connection) -> tuple[int, dict[str, str]]:
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    try:
        schema = int(metadata.get("schema_version", "1"))
    except ValueError as exc:
        raise sqlite3.DatabaseError("invalid index schema_version") from exc
    return schema, metadata


def build_sql(
    args: argparse.Namespace, schema: int, fts_query: str, fetch_limit: int
) -> tuple[str, list[object]]:
    if schema >= 2:
        sql = """
            SELECT
                c.root_label,
                c.relative_path,
                CAST(c.chunk_no AS INTEGER),
                c.source_locator,
                c.heading,
                snippet(chunks, 6, '[', ']', ' … ', 36),
                c.content_sha256,
                c.document_id,
                d.sha256,
                d.vendor,
                d.product,
                d.title,
                d.version,
                d.platform,
                d.os_family,
                d.os_major,
                d.architecture,
                d.hardware_family,
                d.source_status,
                d.classification,
                d.source_url,
                d.published_at,
                d.retrieved_at,
                bm25(chunks, 8.0, 1.0)
            FROM chunks AS c
            JOIN documents AS d ON d.document_id = c.document_id
            WHERE chunks MATCH ?
        """
    else:
        requested_filters = [
            argument_name
            for argument_name in FILTER_ARGUMENTS
            if getattr(args, argument_name) is not None
        ]
        if args.retrieved_after or args.retrieved_before:
            requested_filters.append("retrieved_at")
        if requested_filters:
            raise ValueError(
                "metadata filters require index schema 2; rebuild the private index"
            )
        sql = """
            SELECT
                c.root_label,
                c.relative_path,
                CAST(c.chunk_no AS INTEGER),
                NULL,
                c.heading,
                snippet(chunks, 5, '[', ']', ' … ', 36),
                c.content_sha256,
                c.document_id,
                d.sha256,
                NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                NULL, NULL, NULL, NULL, NULL,
                bm25(chunks, 8.0, 1.0)
            FROM chunks AS c
            JOIN documents AS d ON d.document_id = c.document_id
            WHERE chunks MATCH ?
        """
    parameters: list[object] = [fts_query]
    if args.root:
        placeholders = ",".join("?" for _ in args.root)
        sql += f" AND c.root_label IN ({placeholders})"
        parameters.extend(args.root)
    if schema >= 2:
        for argument_name in FILTER_ARGUMENTS:
            value = getattr(args, argument_name)
            if value is not None:
                sql += f" AND LOWER(d.{argument_name}) = LOWER(?)"
                parameters.append(value)
        if args.retrieved_after:
            sql += " AND d.retrieved_at >= ?"
            parameters.append(args.retrieved_after)
        if args.retrieved_before:
            sql += " AND d.retrieved_at <= ?"
            parameters.append(args.retrieved_before)
    sql += (
        " ORDER BY bm25(chunks, 8.0, 1.0), c.root_label, c.relative_path, "
        "CAST(c.chunk_no AS INTEGER) LIMIT ?"
    )
    parameters.append(fetch_limit)
    return sql, parameters


def run_query(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    schema: int,
    fts_query: str,
) -> list[tuple]:
    fetch_limit = args.limit if args.include_duplicates else min(args.limit * 10, 1000)
    sql, parameters = build_sql(args, schema, fts_query, fetch_limit)
    rows = connection.execute(sql, parameters).fetchall()
    if args.include_duplicates:
        return rows[: args.limit]
    unique: list[tuple] = []
    seen: set[tuple[object, object]] = set()
    for row in rows:
        key = (row[8], row[6])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
        if len(unique) == args.limit:
            break
    return unique


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
        if args.raw_fts_query:
            primary_query = args.query
        else:
            primary_query = safe_fts_query(args.query, "all-terms")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    connection: Optional[sqlite3.Connection] = None
    try:
        connection = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
        schema, metadata = index_schema(connection)
        strategy = "raw" if args.raw_fts_query else "all-terms"
        rows = run_query(connection, args, schema, primary_query)
        if (
            not rows
            and not args.raw_fts_query
            and not args.no_fallback
            and len(query_terms(args.query)) > 1
        ):
            strategy = "any-term-fallback"
            fallback_query = safe_fts_query(args.query, "any-term")
            rows = run_query(connection, args, schema, fallback_query)
        connection.close()
        connection = None
    except (sqlite3.Error, ValueError) as exc:
        if connection is not None:
            connection.close()
        print(f"error: search failed: {exc}", file=sys.stderr)
        return 1

    results = []
    for row in rows:
        (
            root,
            path,
            chunk_no,
            locator,
            heading,
            snippet,
            chunk_hash,
            document_id,
            document_hash,
            vendor,
            product,
            title,
            version,
            platform,
            os_family,
            os_major,
            architecture,
            hardware_family,
            source_status,
            classification,
            source_url,
            published_at,
            retrieved_at,
            score,
        ) = row
        locator_text = f"@{locator}" if locator else ""
        results.append(
            {
                "citation": f"{root}:{path}{locator_text}#chunk-{chunk_no}",
                "root": root,
                "relative_path": path,
                "chunk": chunk_no,
                "source_locator": locator,
                "heading": heading,
                "snippet": snippet,
                "chunk_sha256": chunk_hash,
                "document_sha256": document_hash,
                "document_id": document_id,
                "vendor": vendor,
                "product": product,
                "title": title,
                "version": version,
                "platform": platform,
                "os_family": os_family,
                "os_major": os_major,
                "architecture": architecture,
                "hardware_family": hardware_family,
                "source_status": source_status,
                "classification": classification,
                "source_url": source_url,
                "published_at": published_at,
                "retrieved_at": retrieved_at,
                "score": score,
            }
        )
    output = {
        "bundle_id": metadata.get("bundle_id"),
        "classification": metadata.get("classification"),
        "index_schema_version": schema,
        "query": args.query,
        "strategy": strategy,
        "results": results,
    }
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(
            f"bundle={output['bundle_id'] or 'unknown'} "
            f"classification={output['classification'] or 'unknown'} "
            f"schema={schema} strategy={strategy} results={len(results)}"
        )
        for number, result in enumerate(results, start=1):
            metadata_line = " | ".join(
                str(value)
                for value in (
                    result["vendor"],
                    result["product"],
                    result["version"],
                    result["source_status"],
                )
                if value
            )
            print(f"\n{number}. {result['citation']}")
            print(f"   heading: {result['heading']}")
            if metadata_line:
                print(f"   metadata: {metadata_line}")
            print(f"   document-sha256: {result['document_sha256']}")
            print(f"   chunk-sha256: {result['chunk_sha256']}")
            print(f"   {result['snippet']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
