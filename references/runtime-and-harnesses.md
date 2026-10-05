# Runtime and Harness Integration

## Supported Tool Runtime

The helper scripts run on the approved administration or AI-harness system, not necessarily on the systems being troubleshot.

- Python 3.9 or newer.
- Python's `sqlite3` module with FTS5 enabled.
- No third-party Python packages are required for configuration, indexing, search, cataloging, tests, or Office XML extraction.
- `pdftotext` is required only for PDF extraction.
- `gpgv` is required to verify signed vendor-bundle manifests.

Run the readiness check:

```bash
python3 "$SKILL_ROOT/scripts/doctor.py"
```

`READY` requires an existing mode-restricted configuration, usable labeled roots, at least one supported non-empty search index, SQLite integrity, the expected tables, and FTS5 support. `UNCONFIGURED`, `PARTIALLY_CONFIGURED`, `INVALID`, and `NOT_READY` are not success states.

RHEL 7, 8, 9, and 10 are supported knowledge subjects. The helper runtime does not need to execute on each target. Prefer an approved RHEL 9/10 or other supported management workstation so production targets do not gain unnecessary Python, corpus, or AI dependencies.

## Codex and Claude Code

Both harnesses load `SKILL.md` and can execute the local Python search client. One checkout can serve both skill roots:

```bash
export SKILL_ROOT="${TECH_TROUBLESHOOTER_SKILL_ROOT:-$HOME/.codex/skills/technical-implementation-troubleshooter}"
python3 "$SKILL_ROOT/scripts/install_harness_links.py" --dry-run
python3 "$SKILL_ROOT/scripts/install_harness_links.py"
```

The installer refuses to overwrite a different existing destination. It creates relative symbolic links so Codex and Claude Code resolve the same Git checkout. Restart or reload each harness after installation.

At runtime, resolve `SKILL_ROOT` from the path of the loaded `SKILL.md`. Do not run `python3 scripts/...` relative to the ticket repository. Codex project policy may live in `AGENTS.md`; Claude Code project policy may live in `CLAUDE.md`. Read both when present and apply the instructions governing the file or system in scope.

`agents/openai.yaml` provides Codex-facing metadata. Claude Code may ignore it; portable behavior lives in `SKILL.md` and `references/`.

## Shared Local State

Both harnesses may share:

```text
~/.config/technical-implementation-troubleshooter/config.json
~/.local/share/technical-implementation-troubleshooter/search.sqlite
```

Configuration and index replacement are atomic. Searches open SQLite read-only. Avoid launching two index rebuilds against the same output simultaneously; serialize corpus refresh and promotion through the environment's change workflow.

## Target-System Boundary

Do not install the corpus, indexer, compiler, or AI harness on a production target merely because the skill troubleshoots it. Collect live evidence through an approved administration path. State-changing commands still require task authorization and the target repository's change controls.
