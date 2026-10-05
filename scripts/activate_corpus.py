#!/usr/bin/env python3
"""Configure repositories and activate private corpus roots for the skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


MINIMUM_PYTHON = (3, 9)
CONFIG_SCHEMA_VERSION = 2
SUPPORTED_INDEX_SCHEMAS = {1, 2}
SKILL_NAME = "technical-implementation-troubleshooter"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_DROP_IN = SKILL_DIR / "private-corpus"
DEFAULT_CONFIG = Path.home() / ".config" / SKILL_NAME / "config.json"
DEFAULT_INDEX = Path.home() / ".local" / "share" / SKILL_NAME / "search.sqlite"
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


REPOSITORY_SETTINGS = {
    "technical_implementation_repo": (
        "technical_implementation_repo",
        "TECH_IMPL_REPO",
    ),
    "ansible_repo": ("ansible_repo", "INFRA_ANSIBLE_REPO"),
    "vendor_reference_repo": ("vendor_reference_repo", "VENDOR_REFERENCE_REPO"),
    "wiki_repo": ("wiki_repo", "TECH_IMPL_WIKI_REPO"),
    "md_code_red_repo": ("md_code_red_repo", "MD_CODE_RED_REPO"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Configure repository paths, build the private corpus index, and "
            "register both with the Technical Implementation Troubleshooter skill."
        )
    )
    parser.add_argument(
        "--root",
        action="append",
        metavar="LABEL=PATH",
        help=(
            "Corpus root to activate; repeat for multiple roots. When omitted, "
            "PRIVATE_CORPUS_ROOTS, the local private-corpus directory, or configured "
            "labeled roots are used in that order."
        ),
    )
    parser.add_argument(
        "--bundle",
        action="append",
        type=Path,
        help="Verified immutable private bundle root; repeat for multiple bundles.",
    )
    parser.add_argument(
        "--document-manifest",
        action="append",
        metavar="LABEL=PATH",
        help="Document metadata manifest for a labeled root; repeat as needed.",
    )
    parser.add_argument("--technical-implementation-repo", type=Path)
    parser.add_argument("--ansible-repo", type=Path)
    parser.add_argument("--vendor-reference-repo", type=Path)
    parser.add_argument("--wiki-repo", type=Path)
    parser.add_argument("--md-code-red-repo", type=Path)
    parser.add_argument("--md-code-red-ref")
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help=f"Generated SQLite index path (default: {DEFAULT_INDEX}).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Local configuration path (default: {DEFAULT_CONFIG}).",
    )
    parser.add_argument(
        "--bundle-id",
        default=f"local-corpus-{datetime.now(timezone.utc).date().isoformat()}",
        help="Bundle identifier stored in index metadata.",
    )
    parser.add_argument(
        "--classification",
        choices=("public", "private", "restricted"),
        default="private",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Index .log files after reviewing them for secrets and personal data.",
    )
    parser.add_argument(
        "--allow-sensitive-content",
        action="store_true",
        help=(
            "Allow files containing high-confidence secret patterns. Use only inside "
            "an approved restricted corpus after review."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show resolved roots and output paths without building or writing.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate an existing configuration and index without changing them.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Configure repository and bundle paths without rebuilding the index.",
    )
    return parser.parse_args()


def check_python_version() -> Optional[str]:
    if sys.version_info < MINIMUM_PYTHON:
        return (
            f"Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer is required; "
            f"running {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
    return None


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"root must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid root label: {label!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"corpus root is not a directory: {path}")
    return label, path


def parse_document_manifest(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"document manifest must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"invalid document-manifest label: {label!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"document manifest is not a file: {path}")
    return label, path


def configured_root_specs(config: dict[str, object]) -> list[tuple[str, Path]]:
    raw_roots = config.get("private_reference_roots", [])
    if not isinstance(raw_roots, list):
        raise ValueError("private_reference_roots must be a JSON list")
    roots: list[tuple[str, Path]] = []
    for number, item in enumerate(raw_roots, start=1):
        if isinstance(item, str):
            label = f"corpus-{number}"
            raw_path = item
        elif isinstance(item, dict):
            label = item.get("label")
            raw_path = item.get("path")
            if not isinstance(label, str) or not isinstance(raw_path, str):
                raise ValueError(
                    "private_reference_roots objects require string label and path fields"
                )
            if not LABEL_RE.fullmatch(label):
                raise ValueError(f"invalid configured root label: {label!r}")
        else:
            raise ValueError("private_reference_roots entries must be strings or objects")
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            roots.append((label, path))
    labels = [label for label, _ in roots]
    if len(labels) != len(set(labels)):
        raise ValueError("configured private reference root labels must be unique")
    return roots


def configured_document_manifests(
    config: dict[str, object]
) -> list[tuple[str, Path]]:
    raw_manifests = config.get("private_document_manifests", [])
    if not isinstance(raw_manifests, list):
        raise ValueError("private_document_manifests must be a JSON list")
    manifests: list[tuple[str, Path]] = []
    for item in raw_manifests:
        if not isinstance(item, dict):
            raise ValueError("private_document_manifests entries must be objects")
        label = item.get("label")
        raw_path = item.get("path")
        if not isinstance(label, str) or not isinstance(raw_path, str):
            raise ValueError(
                "private_document_manifests objects require string label and path fields"
            )
        if not LABEL_RE.fullmatch(label):
            raise ValueError(f"invalid configured document-manifest label: {label!r}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"configured document manifest is missing: {path}")
        manifests.append((label, path))
    keys = [(label, str(path)) for label, path in manifests]
    if len(keys) != len(set(keys)):
        raise ValueError("configured document manifests must be unique")
    return manifests


def resolve_document_manifests(
    values: Optional[list[str]],
    config: dict[str, object],
    *,
    roots_were_explicit: bool,
    root_labels: set[str],
) -> list[tuple[str, Path]]:
    if values:
        manifests = [parse_document_manifest(value) for value in values]
    elif roots_were_explicit:
        manifests = []
    else:
        manifests = configured_document_manifests(config)
    for label, _ in manifests:
        if label not in root_labels:
            raise ValueError(f"document manifest uses unknown root label: {label}")
    keys = [(label, str(path)) for label, path in manifests]
    if len(keys) != len(set(keys)):
        raise ValueError("document manifests must be unique")
    return manifests


def resolve_roots(
    values: Optional[list[str]], config: dict[str, object]
) -> list[tuple[str, Path]]:
    configured_roots = configured_root_specs(config)
    if values:
        roots = [parse_root(value) for value in values]
    elif os.environ.get("PRIVATE_CORPUS_ROOTS"):
        roots = []
        for number, item in enumerate(
            os.environ["PRIVATE_CORPUS_ROOTS"].split(os.pathsep), start=1
        ):
            if not item:
                continue
            value = item if "=" in item else f"corpus-{number}={item}"
            roots.append(parse_root(value))
    elif configured_roots:
        roots = configured_roots
    elif DEFAULT_DROP_IN.is_dir():
        roots = [("local-corpus", DEFAULT_DROP_IN.resolve())]
    else:
        roots = []
    labels = [label for label, _ in roots]
    if len(labels) != len(set(labels)):
        raise ValueError("root labels must be unique")
    return roots


def resolve_bundles(
    values: Optional[list[Path]], config: dict[str, object]
) -> list[Path]:
    raw_values: list[object]
    if values:
        raw_values = list(values)
    elif os.environ.get("PRIVATE_CORPUS_BUNDLES"):
        raw_values = [
            value
            for value in os.environ["PRIVATE_CORPUS_BUNDLES"].split(os.pathsep)
            if value
        ]
    else:
        configured = config.get("private_corpus_bundles", [])
        if not isinstance(configured, list):
            raise ValueError("private_corpus_bundles must be a JSON list")
        raw_values = configured
    bundles: list[Path] = []
    for raw_value in raw_values:
        path = Path(str(raw_value)).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"private bundle root is not a directory: {path}")
        bundles.append(path)
    return bundles


def discover_bundle_indexes(bundles: list[Path]) -> list[Path]:
    """Return regular, non-symlink SQLite indexes at documented bundle locations."""
    indexes: list[Path] = []
    for bundle in bundles:
        index_directory = bundle / "indexes"
        preferred = [bundle / "search.sqlite", index_directory / "search.sqlite"]
        candidates = [
            candidate
            for candidate in preferred
            if candidate.is_file() and not candidate.is_symlink()
        ]
        if not candidates:
            discovered = list(bundle.glob("*.sqlite"))
            if index_directory.is_dir() and not index_directory.is_symlink():
                discovered.extend(index_directory.glob("*.sqlite"))
            candidates = [
                candidate
                for candidate in discovered
                if candidate.is_file() and not candidate.is_symlink()
            ]
            if len(candidates) > 1:
                choices = ", ".join(str(path) for path in sorted(candidates))
                raise ValueError(
                    f"bundle contains multiple candidate indexes; name the active one "
                    f"search.sqlite and keep rollback indexes elsewhere: {choices}"
                )
        for candidate in candidates:
            if candidate.is_file() and not candidate.is_symlink():
                resolved = candidate.resolve()
                if resolved not in indexes:
                    indexes.append(resolved)
    return indexes


def apply_repository_settings(
    args: argparse.Namespace, config: dict[str, object]
) -> None:
    for config_key, (argument_name, environment_name) in REPOSITORY_SETTINGS.items():
        explicit = getattr(args, argument_name)
        raw_value = explicit if explicit is not None else os.environ.get(environment_name)
        if raw_value is None:
            continue
        path = Path(raw_value).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"{config_key} is not a directory: {path}")
        config[config_key] = str(path)
    reference = args.md_code_red_ref or os.environ.get("MD_CODE_RED_REF")
    if reference:
        config["md_code_red_ref"] = reference


def load_config(path: Path) -> tuple[dict[str, object], bool]:
    if not path.exists():
        return {"schema_version": CONFIG_SCHEMA_VERSION}, False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read existing configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"existing configuration must contain a JSON object: {path}")
    return value, True


def write_config(path: Path, config: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def fts5_available() -> tuple[bool, Optional[str]]:
    try:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE VIRTUAL TABLE fts5_probe USING fts5(value)")
        connection.close()
        return True, None
    except sqlite3.Error as exc:
        return False, str(exc)


def validate_index(path: Path) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return [f"search index file is missing: {path}"], warnings
    try:
        connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        missing_tables = {"metadata", "documents", "chunks"} - tables
        if missing_tables:
            issues.append(
                f"search index lacks required tables: {', '.join(sorted(missing_tables))}"
            )
            connection.close()
            return issues, warnings
        metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        try:
            schema_version = int(metadata.get("schema_version", "0"))
        except ValueError:
            schema_version = 0
        if schema_version not in SUPPORTED_INDEX_SCHEMAS:
            issues.append(f"unsupported search index schema version: {schema_version}")
        elif schema_version < max(SUPPORTED_INDEX_SCHEMAS):
            warnings.append(
                f"legacy search index schema {schema_version}; rebuild to enable metadata filters"
            )
        document_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(documents)")
        }
        missing_columns = {
            "document_id",
            "root_label",
            "relative_path",
            "sha256",
        } - document_columns
        if missing_columns:
            issues.append(
                f"documents table lacks columns: {', '.join(sorted(missing_columns))}"
            )
        document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if document_count < 1 or chunk_count < 1:
            issues.append("search index contains no searchable documents or chunks")
        connection.close()
    except sqlite3.Error as exc:
        return [f"cannot validate search index {path}: {exc}"], warnings
    if not integrity or integrity[0] != "ok":
        issues.append(f"search index integrity check failed: {path}")
    return issues, warnings


def validate_config(
    config: dict[str, object], *, require_ready: bool
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    schema_version = config.get("schema_version")
    if schema_version not in {1, CONFIG_SCHEMA_VERSION}:
        issues.append(f"unsupported configuration schema_version: {schema_version!r}")
    elif schema_version == 1:
        warnings.append("legacy configuration schema 1; next write will upgrade it")
    for config_key in REPOSITORY_SETTINGS:
        raw_value = config.get(config_key)
        if raw_value and not Path(str(raw_value)).expanduser().is_dir():
            issues.append(f"{config_key} directory is missing: {raw_value}")
    try:
        roots = configured_root_specs(config)
    except ValueError as exc:
        issues.append(str(exc))
        roots = []
    raw_roots = config.get("private_reference_roots", [])
    raw_root_count = len(raw_roots) if isinstance(raw_roots, list) else 0
    if raw_root_count and len(roots) != raw_root_count:
        issues.append("one or more configured private reference roots are missing")
    try:
        manifests = configured_document_manifests(config)
    except ValueError as exc:
        issues.append(str(exc))
        manifests = []
    root_labels = {label for label, _ in roots}
    for label, _ in manifests:
        if label not in root_labels:
            issues.append(f"document manifest uses unknown configured root label: {label}")
    raw_bundles = config.get("private_corpus_bundles", [])
    if not isinstance(raw_bundles, list):
        issues.append("private_corpus_bundles must be a JSON list")
    else:
        for raw_value in raw_bundles:
            if not Path(str(raw_value)).expanduser().is_dir():
                issues.append(f"private bundle directory is missing: {raw_value}")
    raw_indexes = config.get("private_search_indexes", [])
    if not isinstance(raw_indexes, list):
        issues.append("private_search_indexes must be a JSON list")
        raw_indexes = []
    for raw_value in raw_indexes:
        index_issues, index_warnings = validate_index(Path(str(raw_value)).expanduser())
        issues.extend(index_issues)
        warnings.extend(index_warnings)
    if require_ready:
        usable_bundles = isinstance(raw_bundles, list) and bool(raw_bundles)
        if not roots and not usable_bundles:
            issues.append(
                "no usable private_reference_roots or private_corpus_bundles are configured"
            )
        if not raw_indexes:
            issues.append("no private_search_indexes are configured")
    return issues, warnings


def configuration_state(
    *, exists: bool, issues: list[str], ready_required: bool
) -> str:
    if not exists:
        return "UNCONFIGURED"
    if issues:
        readiness_markers = {
            "no usable private_reference_roots or private_corpus_bundles are configured",
            "no private_search_indexes are configured",
        }
        if ready_required and set(issues).issubset(readiness_markers):
            return "PARTIALLY_CONFIGURED"
        return "INVALID"
    return "READY" if ready_required else "CONFIGURED"


def main() -> int:
    version_issue = check_python_version()
    if version_issue:
        print(f"error: {version_issue}", file=sys.stderr)
        return 2
    args = parse_args()
    try:
        config_path = args.config.expanduser().resolve()
        index_path = args.index.expanduser().resolve()
        config, config_exists = load_config(config_path)
        apply_repository_settings(args, config)
        roots = [] if args.check_only else resolve_roots(args.root, config)
        document_manifests = (
            []
            if args.check_only
            else resolve_document_manifests(
                args.document_manifest,
                config,
                roots_were_explicit=args.root is not None,
                root_labels={label for label, _ in roots},
            )
        )
        bundles = [] if args.check_only else resolve_bundles(args.bundle, config)
        bundle_indexes = [] if args.check_only else discover_bundle_indexes(bundles)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check_only:
        if not config_exists:
            print(f"state=UNCONFIGURED config={config_path}", file=sys.stderr)
            print("error: configuration file does not exist", file=sys.stderr)
            return 1
        issues, warnings = validate_config(config, require_ready=True)
        state = configuration_state(exists=True, issues=issues, ready_required=True)
        print(f"state={state} config={config_path}")
        for warning in warnings:
            print(f"warning: {warning}")
        if issues:
            for issue in issues:
                print(f"error: {issue}", file=sys.stderr)
            return 1
        print("configuration check passed")
        return 0

    print("Skill configuration plan")
    for label, path in roots:
        print(f"  root {label}={path}")
    for label, path in document_manifests:
        print(f"  document-manifest {label}={path}")
    for bundle in bundles:
        print(f"  bundle={bundle}")
    for bundle_index in bundle_indexes:
        print(f"  packaged-index={bundle_index}")
    planned_index = "unchanged" if args.skip_index else str(index_path)
    if not roots and bundle_indexes:
        planned_index = "packaged indexes only"
    print(f"  index={planned_index}")
    print(f"  config={config_path}")
    print(f"  bundle-id={args.bundle_id}")
    print(f"  classification={args.classification}")
    if args.dry_run:
        print("dry-run: no index or configuration was written")
        return 0

    available, reason = fts5_available()
    if not available and not args.skip_index:
        print(f"error: Python SQLite lacks FTS5 support: {reason}", file=sys.stderr)
        return 2

    built_index = False
    if not args.skip_index and roots:
        built_index = True
        builder = SCRIPT_DIR / "build_private_search_index.py"
        report_path = index_path.with_suffix(index_path.suffix + ".report.json")
        command = [
            sys.executable,
            str(builder),
            "--output",
            str(index_path),
            "--report",
            str(report_path),
            "--bundle-id",
            args.bundle_id,
            "--classification",
            args.classification,
        ]
        for label, path in roots:
            command.extend(("--root", f"{label}={path}"))
        for label, manifest_path in document_manifests:
            command.extend(("--document-manifest", f"{label}={manifest_path}"))
        if args.include_logs:
            command.append("--include-logs")
        if args.allow_sensitive_content:
            command.append("--allow-sensitive-content")
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(
                "error: corpus indexing failed; local configuration was not changed",
                file=sys.stderr,
            )
            return completed.returncode
    elif not args.skip_index and not bundle_indexes:
        if not roots:
            print(
                f"error: no corpus roots or packaged bundle indexes are available; "
                f"create {DEFAULT_DROP_IN}, pass --root LABEL=PATH, pass --bundle PATH, "
                "or set PRIVATE_CORPUS_ROOTS/PRIVATE_CORPUS_BUNDLES",
                file=sys.stderr,
            )
            return 2

    config["schema_version"] = CONFIG_SCHEMA_VERSION
    if roots:
        config["private_reference_roots"] = [
            {"label": label, "path": str(path)} for label, path in roots
        ]
        config["private_document_manifests"] = [
            {"label": label, "path": str(path)}
            for label, path in document_manifests
        ]
    if bundles:
        config["private_corpus_bundles"] = [str(path) for path in bundles]
    if built_index or bundle_indexes:
        active_indexes = ([index_path] if built_index else []) + bundle_indexes
        config["private_search_indexes"] = [str(path) for path in active_indexes]
    try:
        write_config(config_path, config)
    except OSError as exc:
        print(
            f"error: index was built but configuration could not be written: {exc}",
            file=sys.stderr,
        )
        return 1

    issues, warnings = validate_config(config, require_ready=not args.skip_index)
    state = configuration_state(
        exists=True, issues=issues, ready_required=not args.skip_index
    )
    print(f"state={state}")
    for warning in warnings:
        print(f"warning: {warning}")
    for issue in issues:
        print(f"error: {issue}", file=sys.stderr)
    if issues:
        return 1
    print("configuration complete")
    if built_index:
        print(f"  search: {sys.executable} {SCRIPT_DIR / 'search_private_corpus.py'} \\")
        print(f"    --index {index_path} --query 'your search terms'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
