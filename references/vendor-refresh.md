# Connected Vendor Refresh and Air-Gap Import

Models have training cutoffs. Maintain current vendor knowledge through a controlled reference pipeline rather than relying on model memory.

This workflow supports a complete private corpus. It is not limited to public-redistribution-safe summaries. Preserve full original documents and parsed text when the user lawfully acquired them and is authorized to retain them. Public-export restrictions apply only when content leaves the private corpus.

## Source Policy

Prefer primary vendor sources:

- Red Hat documentation, knowledgebase articles, security advisories, package/repository metadata, and lifecycle pages;
- NVIDIA driver/CUDA repositories, release notes, installation guides, compatibility documentation, and security bulletins;
- Microsoft Learn, Windows release health, security update guidance, protocol specifications, and product lifecycle pages;
- MathWorks release-specific archived documentation, system requirements, product requirements, and installation guidance;
- Jenkins project documentation, security advisories, update-center/plugin metadata, and LTS release notes;
- Ansible/Red Hat Ansible Automation Platform documentation, collection documentation, release notes, and security advisories;
- hardware manufacturer support matrices, firmware advisories, service manuals, and compatibility lists.
- Atlassian Data Center versioned documentation, supported-platform matrices, upgrade notes, security advisories, REST references, lifecycle notices, and installed-app compatibility data;
- vendor package repositories, update-center metadata, release manifests, source repositories at exact tags, and locally generated product metadata such as `ansible-doc --json` or a Jenkins plugin inventory.

Community posts may help form a hypothesis but do not become authoritative offline references without explicit labeling and corroboration.

## Connected-Side Acquisition

Acquire into a quarantine directory first. For each acquired reference, record in `manifest.json` and the source registry:

- stable relative path;
- SHA-256;
- vendor and product;
- title and document type;
- version/release and platform applicability;
- original HTTPS URL;
- publication or last-updated date when supplied;
- retrieval timestamp;
- status: `candidate`, `active`, or `superseded`;
- superseding reference when applicable;
- redistribution or handling note when required.
- data classification: `public`, `private`, or `restricted`;
- acquisition mode: public fetch, authenticated user download, package repository sync, source checkout, local command export, or manual media import;
- content license or terms identifier when known;
- parser name/version and parsed-output path;
- review-by date, reviewer, and supersession relationship.

Use [vendor-manifest.schema.json](vendor-manifest.schema.json) as the machine-readable shape.

Do not circumvent authentication, license, export, or redistribution restrictions. An authorized user may download authenticated or entitled content using the vendor's supported process and place it in the private quarantine directory. The pipeline can then hash, parse, index, and package it without republishing it. If the user is not authorized to retain a source, store permitted metadata and an original summary instead.

## Parse and Index

Preserve the original bytes. Extract a searchable representation without destroying page or heading anchors:

- HTML: store the original page and normalized visible text, title, headings, and canonical URL.
- PDF: store the original PDF and extracted page-separated text; retain page numbers and OCR status.
- Office files: store the original and normalized paragraph/table text with sheet, slide, page, or heading identifiers.
- RPM/repository metadata: preserve signed metadata, package NEVRA, dependencies, module data, file lists, changelogs, keys, and signature results.
- Source repositories: pin the exact commit/tag and record license files; exclude build caches and credentials.
- Command exports: record tool version, command template, execution environment, timestamp, and output hash.

Build the deterministic private SQLite index only from reviewed roots. Optional embeddings may be built inside the target enclave. Never require a cloud embedding service to use the corpus offline.

## Review and Packaging

Before export:

1. Confirm the source domain and TLS retrieval path.
2. Check the document applies to the versions actually operated.
3. Distinguish current, archived release-specific, preview, and superseded material.
4. Scan the bundle using the approved security process.
5. Generate hashes and the manifest after final content selection.
6. Sign or otherwise attest the bundle using the organization's approved mechanism.
7. Record the refresh/change identifier and reviewer.

## Air-Gap Import

On the offline side:

1. Follow the approved media-ingress process.
2. Verify the bundle signature/attestation when the publishing process provides one, then verify the SHA-256 manifest before activation. Do not describe a bare checksum as publisher authentication.
3. Run `scripts/verify_vendor_bundle.py` with the detached manifest signature and trusted public-key keyring. Production activation requires successful signature verification; `--allow-unsigned` is an explicit development/personal exception, not an authentication substitute.
4. Import into a new immutable/versioned bundle directory.
5. Change the `active` pointer only after review.
6. Retain or archive the prior bundle according to records policy.
7. Rebuild the metadata catalog and full-text index, then run representative retrieval tests that confirm citations resolve to the imported sources.

Do not update active references in place during a troubleshooting event.

## Freshness

Set review intervals by volatility and risk. At minimum, refresh or revalidate before a material change involving:

- OS minor releases, kernels, or support lifecycle;
- GPU drivers, CUDA, firmware, or hardware enablement;
- Microsoft cumulative updates, AD security changes, or certificate behavior;
- MATLAB releases and GPU/toolchain compatibility;
- Jenkins core or plugin upgrades;
- Ansible core/automation platform or collection upgrades;
- security advisories relevant to the environment.

An old reference can remain useful when it is explicitly tied to an old installed version. Staleness is a problem when applicability is unknown, not merely when a document is old.

## Refresh Workers and Review

Use narrow stages instead of an agent that silently “learns” into trusted guidance:

1. discovery detects new releases, advisories, lifecycle changes, or changed pages;
2. acquisition downloads to quarantine and records hashes and terms;
3. parsing produces candidate text and normalized records;
4. comparison reports changed facts, removed sections, and contradictions;
5. technical review verifies version applicability and command safety;
6. promotion changes candidate records to active;
7. release creates a new immutable private bundle, manifest, coverage report, and index.

Every stage should be restartable and idempotent. A parser that unexpectedly yields zero records or a mutable URL that changes product version is a review failure, not a successful refresh.
