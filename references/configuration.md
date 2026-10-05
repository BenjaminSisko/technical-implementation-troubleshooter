# Repository and Knowledge-Root Configuration

The skill separates portable operating instructions from environment-specific paths. Resolve roots in this order:

1. Exact paths supplied by the user for the current task.
2. Repository paths already established by trusted task context.
3. Environment variables:
   - `TECH_IMPL_REPO`: Technical Implementation tickets, runbooks, decisions, and documentation.
   - `INFRA_ANSIBLE_REPO`: Ansible inventories, collections, roles, and playbooks.
   - `VENDOR_REFERENCE_REPO`: approved offline vendor-reference bundles and manifests.
   - `TECH_IMPL_WIKI_REPO`: wiki repository, only when it is a distinct checkout.
   - `MD_CODE_RED_REPO`: MD CODE RED source repository containing the offline RHEL/Ansible corpus.
   - `MD_CODE_RED_REF`: approved commit, tag, or remote-tracking ref to query. Do not assume the working-tree branch is current.
   - `PRIVATE_CORPUS_ROOTS`: platform-separated list of approved private document roots, used only when an environment cannot use the configuration file.
   - `PRIVATE_CORPUS_BUNDLES`: platform-separated list of immutable imported bundle roots.
4. A user-approved local configuration file at `~/.config/technical-implementation-troubleshooter/config.json`.

Do not broadly scan a home directory, mount tree, or filesystem to guess a production repository. Do not use a similarly named personal or test repository in place of the work repository.

## Simple Corpus Activation

The supported one-command setup is:

```bash
python3 scripts/configure_skill.py
```

With no arguments, the helper indexes the skill's Git-ignored `private-corpus/` directory using the root label `local-corpus`. To leave source files in an existing approved location, repeat `--root LABEL=PATH`:

```bash
python3 scripts/configure_skill.py \
  --root vendor=/approved/corpus/vendor \
  --root environment=/approved/corpus/environment
```

Unless overridden, the helper writes:

- the generated search index to `~/.local/share/technical-implementation-troubleshooter/search.sqlite`;
- local path configuration to `~/.config/technical-implementation-troubleshooter/config.json`.

It preserves unrelated keys in an existing configuration and replaces only `private_reference_roots` and `private_search_indexes`. The update is atomic. Use `--dry-run` to print the planned roots and paths without building or writing anything.

The helper can configure the named repositories with `--technical-implementation-repo`, `--ansible-repo`, `--vendor-reference-repo`, `--wiki-repo`, `--md-code-red-repo`, and `--md-code-red-ref`. It uses the corresponding environment variables when a flag is absent. Use `--skip-index` to update repository settings without rebuilding the corpus and `--check-only` to verify configured directories and SQLite integrity.

## Optional Configuration File

The configuration file contains paths and non-secret policy selectors only:

```json
{
  "schema_version": 1,
  "technical_implementation_repo": "/absolute/path/to/Technical Implementation",
  "ansible_repo": "/absolute/path/to/ansible-repository",
  "vendor_reference_repo": "/absolute/path/to/vendor-reference-repository",
  "wiki_repo": "/absolute/path/to/wiki-repository",
  "md_code_red_repo": "/absolute/path/to/md-code-red",
  "md_code_red_ref": "refs/remotes/origin/main",
  "private_reference_roots": [
    "/absolute/private/path/environment-overlay",
    "/absolute/private/path/vendor-extracts"
  ],
  "private_corpus_bundles": [
    "/absolute/private/path/bundles/2026-10-04"
  ],
  "private_search_indexes": [
    "/absolute/private/path/bundles/2026-10-04/indexes/search.sqlite"
  ],
  "wiki_publish_command": null,
  "default_ticket_area": null
}
```

Do not place tokens, passwords, private keys, Ansible Vault passwords, license content, or Git credentials in this file. Paths in this file may reveal workstation or organization details, so do not publish the live configuration. Publish a placeholder-only example instead.

## Layer Order

Resolve and search knowledge in this order:

1. Portable skill policy and schemas.
2. Pinned public or internally approved knowledge packs.
3. Authorized private vendor bundles containing full acquired source and parsed text.
4. Private environment overlay containing inventory, tickets, host evidence, and local procedures.

Layer order is not evidence precedence. Fresh live evidence and validated desired state still outrank a document merely because the document is in a later layer. Record contradictions instead of overwriting one layer with another.

Do not scan every configured private root automatically for every ticket. Select roots by domain and classification, then search the generated full-text index. This reduces irrelevant retrieval and limits accidental disclosure.

## Repository Discovery Within a Known Root

After resolving a root, use `rg --files` and targeted `rg` searches to locate:

- `AGENTS.md` and nested instruction files;
- ticket and troubleshooting templates;
- runbook indexes;
- working agreements and contribution rules;
- change, approval, and decision templates;
- wiki synchronization scripts;
- Ansible inventory, `ansible.cfg`, requirements files, roles, and playbooks;
- MD CODE RED release facts, provenance, curated datasets, host captures, raw-source manifests, candidate records, QA gates, and residual/gap records;
- vendor bundle manifests and active/superseded markers.

Read the repository's own conventions before creating names, directories, identifiers, branches, commits, or wiki pages.

## Expected Logical Roles

Physical layouts may differ, but keep these roles distinct:

- **Case record:** evolving event history, evidence, hypotheses, decisions, commands, and outcome.
- **Runbook/known issue:** reviewed reusable procedure or diagnosis, constrained by version and environment.
- **Inventory/configuration:** current facts about systems and intended state.
- **Ansible:** executable desired state and repeatable remediation.
- **Wiki:** reader-facing publication derived from canonical repository sources when possible.
- **Vendor references:** immutable or versioned external evidence with provenance and integrity metadata.
- **MD CODE RED:** offline discovery and command-reference corpus. It is neither the affected host's live state nor the production Ansible repository.

If one repository serves multiple roles, preserve the conceptual separation in its existing structure.
