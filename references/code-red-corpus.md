# MD CODE RED Offline Corpus Router

Use this reference for RHEL/Linux and Ansible tickets. MD CODE RED already contains the extracted material that should support this troubleshooting skill. Keep the corpus in its source repository; do not copy its thousands of records into this skill.

## Resolve the Repository and Ref

Resolve `MD_CODE_RED_REPO` and `MD_CODE_RED_REF` by the rules in [configuration.md](configuration.md). Do not embed a user's checkout path, remote name, or current commit in the portable skill. Pin the approved release and artifact digest in the private bundle's dependency lock.

Before using the corpus:

```bash
git -C "$MD_CODE_RED_REPO" status --short --branch
git -C "$MD_CODE_RED_REPO" rev-parse --verify "$MD_CODE_RED_REF^{commit}"
git -C "$MD_CODE_RED_REPO" show "$MD_CODE_RED_REF:docs/generated/RELEASE_FACTS.md"
git -C "$MD_CODE_RED_REPO" show "$MD_CODE_RED_REF:extract/ingest_notes.md"
```

Record the resolved commit in the ticket. Query the selected ref with `git grep` and `git show` if the working tree is on another branch; do not switch branches, overwrite a dirty tree, or silently query stale checked-out files.

## What the Corpus May Contain

Inspect the selected ref's release facts and provenance rather than assuming a historical count. Depending on release, the repository may contain:

- Ansible module and CLI metadata tied to an exact `ansible-core` version.
- Curated RHEL command, error, checklist, tree, reference, and troubleshooting datasets under `content/`.
- RHEL 7, 8, 9, and 10 versioned flag dictionaries and raw `man`/`--help` captures under `content-src/raw/rhel*/`, with per-release manifests.
- Mined command candidates from Red Hat documentation under `content-src/raw/redhat/rhel*.candidates.jsonl`.
- DISA RHEL 7–10 STIG XCCDF sources, CCI material, generated rules, checksums, and mapping data.
- Lab or real-host execution captures and verification receipts under test paths.
- Residual/gap datasets under `content-src/residue/`.
- Provenance, QA gates, release facts, security reviews, and known limitations under `docs/`.

Deeper upstream documentation or extracted corpora may be stored separately. Resolve those only through configured private roots and verified manifests; do not invent or broadly search for a storage location during an incident.

## Trust and Permitted Use

Use the narrowest matching layer:

1. **Real-host capture plus receipt** — strongest Code Red evidence for the recorded command, RHEL release, package state, host, and date. It does not automatically generalize to another minor release or environment.
2. **Curated content** — suitable for offline discovery and forming a diagnostic plan when its provenance and RHEL applicability match. A QA pass proves defined structural properties; it does not prove every command is operationally correct on the current host.
3. **Raw RHEL `man`/`--help` capture** — suitable for exact option and syntax evidence for the recorded package/release. Check its manifest and package metadata before applying it elsewhere.
4. **STIG source and generated rule data** — suitable for control identification and check/fix analysis at the pinned STIG release. It is not automatic authorization to remediate.
5. **Mined Red Hat command candidate** — discovery lead only. Candidate records intentionally omit surrounding prose and therefore omit prerequisites, warnings, branching, and applicability. Never execute one directly from the candidate file.
6. **Residue/gap record** — an explicit sign that coverage is missing or unresolved. Preserve the gap and obtain better evidence.

Read the selected release's coverage report before claiming host validation. The presence of RHEL man pages, flags, STIG rules, or mined documentation is not proof that a procedure was executed on that release.

## Search Patterns

Start broad enough to find related evidence, then inspect the record and its source:

```bash
git -C "$MD_CODE_RED_REPO" grep -n -i -- "$TERM" "$MD_CODE_RED_REF" -- \
  content content-src tests/captures docs

git -C "$MD_CODE_RED_REPO" show \
  "$MD_CODE_RED_REF:content/rhel_troubleshooting.json"
```

For Ansible, search the FQCN, short module name, parameter, error text, and installed collection version. For RHEL, search the exact major release, command, option, package NEVRA, service, error text, STIG ID, and subsystem. Prefer the matching version-specific record over a cross-version command.

## Relationship to the Automation Repository

The Code Red Ansible corpus describes modules, CLIs, and safe composition patterns. The configured `INFRA_ANSIBLE_REPO` owns the actual inventory, variables, roles, playbooks, and desired state. Never infer that a Code Red example is deployed merely because it exists in the corpus.

Never substitute a personal, lab, or similarly named Ansible checkout for the affected environment's automation repository. Preserve unrelated changes and resolve the production repository explicitly.

## Relationship to Vendor References

Code Red is an offline index and working corpus, but it does not replace an approved, versioned vendor-reference bundle. When exact support status, errata, lifecycle, compatibility, or newly released behavior matters, corroborate with the imported vendor source and record its retrieval date and hash. If the connected-side source is newer, update the governed corpus through its ingestion and QA workflow rather than hand-editing generated files.

## Publication Boundary

Some Code Red releases may include raw host captures, generated copies of those captures, internal names, addresses, accounts, package inventories, or other operational details that ordinary secret scanners do not flag. Those records may remain useful in a personal private corpus, but they are private evidence. Do not publish the tree, generated HTML, release archive, or Git history until an operational-information review proves the selected public export contains only sanitized fixtures and receipts.
