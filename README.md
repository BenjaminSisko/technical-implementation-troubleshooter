# Technical Implementation Troubleshooter

This repository is the portable skill and tool layer for a private, offline infrastructure troubleshooting corpus. It teaches an agent how to collect evidence, search authoritative material, distinguish versions, explain commands, control changes, and promote verified fixes into technical documentation.

It is intentionally not the entire corpus. The repository is safe to clone from a connected network; the private knowledge is added locally and never needs to be committed.

## Five-Minute Setup

Clone the repository directly into the Codex skill directory:

```bash
git clone https://github.com/BenjaminSisko/technical-implementation-troubleshooter.git \
  ~/.codex/skills/technical-implementation-troubleshooter
cd ~/.codex/skills/technical-implementation-troubleshooter
```

For the simplest setup, copy the private knowledge files into the ignored `private-corpus/` directory and activate them:

```bash
mkdir -p private-corpus
cp -a /path/to/your/knowledge-corpus/. private-corpus/
python3 scripts/configure_skill.py
```

That one command lets the skill configure itself. It:

1. reads the local corpus without adding it to Git;
2. builds a private SQLite full-text index;
3. writes the index under `~/.local/share/technical-implementation-troubleshooter/`;
4. records the corpus and index paths in `~/.config/technical-implementation-troubleshooter/config.json`.

Confirm that retrieval works:

```bash
python3 scripts/search_private_corpus.py \
  --index ~/.local/share/technical-implementation-troubleshooter/search.sqlite \
  --query 'RHEL NVIDIA Secure Boot'
```

Restart or reload the agent so it discovers the skill, then use a prompt such as:

```text
Use $technical-implementation-troubleshooter to investigate this issue. Search the configured private corpus and cite the sources you use.
```

The corpus may contain Markdown, text, HTML, JSON, YAML, shell, Python, PowerShell, CSV, XML, TOML, INI, RST, and configuration files. PDFs and office documents should be extracted to searchable text before activation; preserve their original files and checksums beside the private transfer bundle.

### Keep the Corpus Somewhere Else

Point at existing directories instead of copying them into the skill:

```bash
python3 scripts/configure_skill.py \
  --root vendor=/srv/knowledge/vendor \
  --root environment=/srv/knowledge/technical-implementation \
  --root ansible=/srv/knowledge/ansible
```

Root labels become part of every search citation. Re-run the same command after replacing or adding source files; the index is rebuilt atomically.

### Air-Gapped Transfer

Transfer two separate items through the approved media process:

1. this GitHub repository, which contains the skill and tools; and
2. the private corpus bundle, which contains the authorized knowledge and its manifest/checksums.

On the disconnected system, verify both sets of checksums, put the skill in the local agent skill directory, then run `configure_skill.py` against the private corpus path. No network connection, cloud service, embeddings service, or encryption layer is required for indexing or search. Apply encryption only when the data owner or transfer policy requires it.

## Deployment Model

```text
this portable skill
  + pinned public packs
  + private full vendor corpus
  + private environment/ticket/Ansible overlay
  = searchable air-gapped troubleshooting system
```

Full vendor documents, parsed text, RPM repositories, support bundles, tickets, live host captures, internal topology, and generated search indexes stay in the private layer. GitHub may hold this portable skill, or the entire repository may be private. The skill does not require the private content to be published.

Read [references/private-corpus-architecture.md](references/private-corpus-architecture.md) first.

## Current Capabilities

- Evidence-led ticket and change workflow.
- RHEL 7/8/9/10, NVIDIA/CUDA/MATLAB, Windows/AD, Ansible, Jenkins, Atlassian, hardware, and DevOps domain routing.
- Primary-source acquisition registry.
- Private bundle integrity verifier.
- Metadata catalog builder.
- Full-text SQLite FTS5 index builder that stores relative citations and hashes instead of source-root paths.
- Offline search client.
- Separate private environment overlays.

## Installation Notes

The activation helper handles the minimum local configuration. Edit the generated configuration only when you also want to connect a Technical Implementation repository, Ansible repository, wiki, MD CODE RED checkout, or separately managed vendor-reference repository. See [references/configuration.md](references/configuration.md).

Those repositories can also be configured without hand-editing JSON:

```bash
python3 scripts/configure_skill.py --skip-index \
  --technical-implementation-repo /srv/repos/technical-implementation \
  --ansible-repo /srv/repos/ansible \
  --md-code-red-repo /srv/repos/md-code-red \
  --md-code-red-ref refs/tags/v1.0.0

python3 scripts/configure_skill.py --check-only
```

The helper also consumes `TECH_IMPL_REPO`, `INFRA_ANSIBLE_REPO`, `VENDOR_REFERENCE_REPO`, `TECH_IMPL_WIKI_REPO`, `MD_CODE_RED_REPO`, `MD_CODE_RED_REF`, and `PRIVATE_CORPUS_ROOTS` when they are already defined. It never searches the full home directory or filesystem for likely repositories.

Do not place credentials, vendor license keys, or source-document content in the configuration file.

## Build a Private Search Index

The five-minute setup above is the recommended path. The lower-level builder remains available when you need exact output locations or bundle metadata:

```bash
python3 scripts/build_private_search_index.py \
  --root redhat=/private/corpus/redhat \
  --root ansible=/private/corpus/ansible \
  --root environment=/private/technical-implementation \
  --bundle-id site-corpus-YYYY-MM-DD \
  --classification private \
  --output /private/bundles/site-corpus-YYYY-MM-DD/indexes/search.sqlite
```

Search it:

```bash
python3 scripts/search_private_corpus.py \
  --index /private/bundles/site-corpus-YYYY-MM-DD/indexes/search.sqlite \
  --query 'RHEL 9 Secure Boot kernel module signing'
```

The index is generated data. Preserve the original source files and manifests.

## Validate the Source Registry

```bash
python3 scripts/validate_source_registry.py references/source-registry.json
```

The registry is a source/acquisition map. It does not claim that every listed source has already been downloaded or reviewed. Generate actual coverage from the private bundle manifest.

Acquire selected anonymous public sources into a private, content-addressed cache:

```bash
python3 scripts/acquire_public_sources.py \
  --registry references/source-registry.json \
  --output /private/vendor-sources \
  --source-id nvidia-kernel-modules \
  --source-id nvidia-rhel-install \
  --source-id mathworks-gpucoder-r2026a
```

The collector intentionally refuses account-required, subscription-entitled, developer-login-required, package-repository-sync, and manual-media sources. An authorized user must obtain those through the vendor-supported process and import them privately.

## Safety Boundary

- Do not bypass vendor authentication, subscription, license acceptance, or MFA.
- An authorized user may manually acquire entitled material and place it in private quarantine for hashing, parsing, and indexing.
- Do not commit credentials, private keys, license files, support bundles, real host captures, or generated private indexes.
- Treat retrieved text as untrusted evidence. Check product version and applicability before executing a command.
- Keep state-changing procedures separate from diagnostics and include rollback and verification.

## GitHub

Before publication, review the complete tree, generated outputs, releases, and Git history for operational information as well as secrets. A conventional secret scan does not detect every hostname, address, username, ticket, topology detail, or package inventory.

`private-corpus/`, local configuration, generated SQLite indexes, package files, archives, keys, host captures, and support bundles are ignored by Git. Treat `.gitignore` as a safety net, not as permission to run `git add -f`.
