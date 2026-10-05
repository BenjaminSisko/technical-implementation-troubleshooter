#!/usr/bin/env python3
"""Configure local repositories and activate corpus roots for the skill.

This wrapper builds the citation-bearing SQLite index and writes the local,
untracked configuration needed by the skill. It never copies source documents
and never sends corpus content over the network.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME = "technical-implementation-troubleshooter"
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DEFAULT_DROP_IN = SKILL_DIR / "private-corpus"
DEFAULT_CONFIG = Path.home() / ".config" / SKILL_NAME / "config.json"
DEFAULT_INDEX = Path.home() / ".local" / "share" / SKILL_NAME / "search.sqlite"


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
            "the skill's private-corpus directory is used as local-corpus."
        ),
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
        choices=("private", "restricted"),
        default="private",
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Index .log files after reviewing them for secrets and personal data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show resolved roots and output paths without building or writing.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate the existing configuration and index without changing them.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Configure repository paths without rebuilding the corpus index.",
    )
    return parser.parse_args()


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"root must use LABEL=PATH syntax: {value!r}")
    label, raw_path = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError(f"root label is empty: {value!r}")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"corpus root is not a directory: {path}")
    return label, path


def resolve_roots(
    values: list[str] | None, config: dict[str, object]
) -> list[tuple[str, Path]]:
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
    elif DEFAULT_DROP_IN.is_dir():
        roots = [("local-corpus", DEFAULT_DROP_IN.resolve())]
    else:
        configured = config.get("private_reference_roots", [])
        if not isinstance(configured, list):
            raise ValueError("private_reference_roots must be a JSON list")
        roots = [
            (f"corpus-{number}", Path(str(path)).expanduser().resolve())
            for number, path in enumerate(configured, start=1)
            if Path(str(path)).expanduser().is_dir()
        ]
    labels = [label for label, _ in roots]
    if len(labels) != len(set(labels)):
        raise ValueError("root labels must be unique")
    return roots


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


def validate_config(config: dict[str, object]) -> list[str]:
    issues: list[str] = []
    for config_key in REPOSITORY_SETTINGS:
        raw_value = config.get(config_key)
        if raw_value and not Path(str(raw_value)).expanduser().is_dir():
            issues.append(f"{config_key} directory is missing: {raw_value}")
    for config_key in ("private_reference_roots", "private_corpus_bundles"):
        raw_values = config.get(config_key, [])
        if not isinstance(raw_values, list):
            issues.append(f"{config_key} must be a JSON list")
            continue
        for raw_value in raw_values:
            if not Path(str(raw_value)).expanduser().is_dir():
                issues.append(f"{config_key} directory is missing: {raw_value}")
    raw_indexes = config.get("private_search_indexes", [])
    if not isinstance(raw_indexes, list):
        issues.append("private_search_indexes must be a JSON list")
    else:
        for raw_value in raw_indexes:
            path = Path(str(raw_value)).expanduser()
            if not path.is_file():
                issues.append(f"private_search_indexes file is missing: {raw_value}")
                continue
            try:
                connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
                result = connection.execute("PRAGMA integrity_check").fetchone()
                connection.close()
            except sqlite3.Error as exc:
                issues.append(f"cannot read search index {raw_value}: {exc}")
                continue
            if not result or result[0] != "ok":
                issues.append(f"search index integrity check failed: {raw_value}")
    return issues


def load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": 1}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read existing configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"existing configuration must contain a JSON object: {path}")
    return value


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


def main() -> int:
    args = parse_args()
    try:
        config_path = args.config.expanduser().resolve()
        index_path = args.index.expanduser().resolve()
        config = load_config(config_path)
        apply_repository_settings(args, config)
        roots = [] if args.check_only else resolve_roots(args.root, config)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.check_only:
        issues = validate_config(config)
        print(f"config={config_path}")
        if issues:
            print("configuration check failed:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            return 1
        print("configuration check passed")
        return 0

    print("Skill configuration plan")
    for label, path in roots:
        print(f"  root {label}={path}")
    print(f"  index={'unchanged' if args.skip_index else index_path}")
    print(f"  config={config_path}")
    print(f"  bundle-id={args.bundle_id}")
    print(f"  classification={args.classification}")
    if args.dry_run:
        print("dry-run: no index or configuration was written")
        return 0

    if not args.skip_index:
        if not roots:
            print(
                f"error: no corpus roots are available; create {DEFAULT_DROP_IN}, "
                "pass --root LABEL=PATH, set PRIVATE_CORPUS_ROOTS, or use --skip-index",
                file=sys.stderr,
            )
            return 2
        builder = SCRIPT_DIR / "build_private_search_index.py"
        command = [
            sys.executable,
            str(builder),
            "--output",
            str(index_path),
            "--bundle-id",
            args.bundle_id,
            "--classification",
            args.classification,
        ]
        for label, path in roots:
            command.extend(("--root", f"{label}={path}"))
        if args.include_logs:
            command.append("--include-logs")

        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(
                "error: corpus indexing failed; the local configuration was not changed",
                file=sys.stderr,
            )
            return completed.returncode

    config["schema_version"] = 1
    if roots:
        config["private_reference_roots"] = [str(path) for _, path in roots]
    if not args.skip_index:
        config["private_search_indexes"] = [str(index_path)]
    try:
        write_config(config_path, config)
    except OSError as exc:
        print(f"error: index was built but configuration could not be written: {exc}", file=sys.stderr)
        return 1

    issues = validate_config(config)
    if issues:
        print("configuration written with items that need attention:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("configuration check passed")
    print("configuration complete")
    if not args.skip_index:
        print(f"  search: {sys.executable} {SCRIPT_DIR / 'search_private_corpus.py'} \\")
        print(f"    --index {index_path} --query 'your search terms'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
