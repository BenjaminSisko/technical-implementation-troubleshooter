# Wiki and Ansible Integration

## Canonical Ownership

Determine which repository owns each artifact before editing:

- ticket/event history and command log: Technical Implementation;
- reusable runbook/known issue: Technical Implementation unless local instructions say otherwise;
- desired configuration and repeatable remediation: Ansible repository;
- reader-facing wiki: generated or synchronized from the canonical source when possible;
- vendor evidence: vendor-reference repository/bundle.

Do not create competing copies of the same procedure.

## Cross-Repository Change Record

When one troubleshooting event changes more than one repository, cross-link:

- ticket/change identifier;
- Technical Implementation commit or review;
- Ansible commit or review;
- wiki publication commit/job;
- affected inventory/assets;
- verification evidence and date.

Do not claim the wiki or automation is updated until the corresponding commit, review, or publication job exists and succeeds.

## Ansible Promotion

Promote a manual fix into Ansible when it represents desired, repeatable state. Preserve:

- idempotency;
- supported platform/version conditions;
- handlers and restart boundaries;
- validation and rollback;
- inventory/variable ownership;
- secret separation;
- check/lint/test evidence;
- staged deployment strategy.

Keep incident-specific forensic collection out of a permanent enforcement role unless it has a defined operational purpose.

## Wiki Publication

Use the existing wiki workflow discovered in repository instructions. The workflow may be a wiki Git repository, generated site, CI job, or sync script. Do not guess the platform from the word “wiki.”

Before publication:

- remove secrets, internal-only evidence, transient hypotheses, and sensitive identifiers according to policy;
- preserve links back to the canonical ticket/runbook where permitted;
- include version/applicability and last-verified information;
- confirm superseded pages redirect or link to current guidance.

Publication is an external mutation. Perform it only when the current request or standing trusted instruction authorizes it.
