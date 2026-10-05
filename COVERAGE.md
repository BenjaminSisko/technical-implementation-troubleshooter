# Coverage

Status as of 2026-10-04: public dual-harness skill and private schema-2 retrieval foundation operational.

## Implemented

- Portable evidence hierarchy, ticket workflow, knowledge promotion, and teaching standard.
- Public/private corpus separation and private full-source retention model.
- Source registry with 50 official entry points across Red Hat, NVIDIA, CUDA, MathWorks, Ansible/AAP, Jenkins, Atlassian, Microsoft, and HPE, including authenticated-source acquisition records.
- Registry validation.
- Metadata-only inventory catalog.
- Private SQLite FTS5 schema-2 indexing with citation-bearing search, structured applicability metadata, stable labeled roots, metadata filters, duplicate suppression, and deterministic any-term fallback.
- Explicit readiness states and a doctor command covering Python, FTS5, configuration, permissions, index schema, non-empty content, and SQLite integrity.
- Shared-checkout Codex and Claude Code installation without duplicate skill copies.
- Offline PDF/DOCX/PPTX/XLSX text extraction with page/slide/sheet separators and hash-bearing receipts.
- Default quarantine of common secret filenames and high-confidence secret content, with a private ingestion report and explicit restricted-corpus override.
- Detached OpenPGP manifest verification required for normal bundle activation; unsigned use requires an explicit exception.
- Governed knowledge-candidate generation that never silently activates a case resolution.
- Automated Python 3.9/3.11/3.13 integration tests and tracked-payload boundary checks.
- Content-addressed anonymous public-source acquisition with source receipts and an access-class refusal gate.
- Domain routing for RHEL 7/8/9/10; NVIDIA on RHEL 8/9/10; MATLAB; Windows/AD; Ansible; Jenkins; Atlassian Data Center; and cross-platform integrations.

## Private Corpus Activated on the Development Workstation

The private configuration points to the existing mounted ANVIL corpus. Its active schema-2 index contains 33,593 documents and 246,834 chunks from the extracted, directly searchable original, manifest, pinned vendor-source, current vendor-page, and private environment-overlay trees. The exact path and operational details live in the private overlay, not this portable file. The previous schema-1 index is retained privately as a rollback artifact and is not active.

An initial private current-vendor cache contains 11 complete NVIDIA and MathWorks R2026a/R2026b source pages with retrieval receipts and SHA-256 values. Authenticated/entitled sources remain a manual-authorized acquisition backlog.

## Existing Private-Corpus Strengths

- Red Hat product documentation and local manuals.
- Ansible and AAP source/documentation.
- Microsoft, DISA, NIST/OSCAL, CISA, FedRAMP, JSIG, VMware, Git, and ComplianceAsCode material.

## Acquisition Backlog

The activated corpus must not yet be called complete for:

- current NVIDIA RHEL 8/9/10 repositories, release/lifecycle/security material, CUDA, cuDNN, TensorRT, and hardware guidance;
- MathWorks release-archived MATLAB/Parallel Computing Toolbox/Deep Learning Toolbox/GPU Coder matrices and authorized installer material;
- Jenkins current LTS/Java/plugin/update-center/security/offline-operation set;
- product/version-specific Atlassian Jira, JSM, Confluence, Bitbucket, Crowd, Bamboo, Fisheye, and Crucible Data Center material;
- full current Windows Server/AD and HPE platform material;
- exact production Ansible execution-environment and installed-collection exports.

These are source acquisition and review tasks. The skill must report a missing source rather than filling a gap from model memory.

## Production-Maturity Gaps

- Organizational signing-key issuance, rotation, revocation, and approval policy remain environment responsibilities even though the verifier now requires a detached signature by default.
- PDF extraction depends on an approved local `pdftotext`; Office extraction is intentionally basic XML text extraction and does not reproduce visual layout or execute macros.
- Public GitHub history exists and is scanned before release. GitHub publication and offline-corpus promotion follow [references/release-integrity.md](references/release-integrity.md); organization-controlled release-signing keys remain an environment responsibility.
- The generic metadata schema is operational; richer domain compatibility graphs, semantic-diff workers, and complete behavioral agent evaluations remain future work.
- Content-pattern quarantine is deliberately high-confidence and is not a replacement for the organization's approved malware, DLP, privacy, or media-ingress controls.
