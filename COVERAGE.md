# Coverage

Status as of 2026-10-04: foundation and first private index operational.

## Implemented

- Portable evidence hierarchy, ticket workflow, knowledge promotion, and teaching standard.
- Public/private corpus separation and private full-source retention model.
- Source registry with 50 official entry points across Red Hat, NVIDIA, CUDA, MathWorks, Ansible/AAP, Jenkins, Atlassian, Microsoft, and HPE, including authenticated-source acquisition records.
- Registry validation.
- Metadata-only inventory catalog.
- Private SQLite FTS5 indexing and citation-bearing search.
- Content-addressed anonymous public-source acquisition with source receipts and an access-class refusal gate.
- Domain routing for RHEL 7/8/9/10; NVIDIA on RHEL 8/9/10; MATLAB; Windows/AD; Ansible; Jenkins; Atlassian Data Center; and cross-platform integrations.

## Private Corpus Activated on the Development Workstation

The private configuration points to the existing mounted ANVIL corpus. Its generated index contains 33,621 documents and 212,940 chunks from the extracted, directly searchable original, manifest, pinned vendor-source, current vendor-page, and private environment-overlay trees. The exact path and operational details live in the private overlay, not this portable file.

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

- Bundle manifest signature verification is not yet mandatory.
- PDF/Office parsing is expected upstream; the indexer currently consumes text, Markdown, HTML, JSON, YAML, XML, source, and similar UTF-8-compatible formats.
- Public release history has not been created or audited.
- Domain-specific fact/procedure schemas, compatibility graph, semantic-diff workers, and complete agent evals remain future work.
- No public GitHub repository has been created or pushed by this build.
