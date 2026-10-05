# Evidence-Led Troubleshooting Operating Model

## Intake

Capture the user's report without prematurely translating it into a cause:

- ticket or incident identifier;
- affected users, systems, sites, and services;
- first observed time and whether the condition is continuous or intermittent;
- business/mission impact;
- exact error text and where it appeared;
- last known good time;
- recent authorized or observed changes;
- required success condition;
- maintenance, reboot, outage, and access constraints.

Separate facts provided by the reporter from assumptions introduced during triage.

## Baseline

Collect only evidence relevant to the symptom. Typical baseline dimensions are:

- hardware identity and topology;
- firmware and boot security where relevant;
- OS edition, release/build, architecture, and kernel;
- installed and running package/application versions;
- service state and dependency state;
- configuration source and drift from automation;
- network path, DNS, time, certificate, and authentication state;
- resource capacity and recent error logs.

Prefer commands that are available by default on the exact platform. Do not install diagnostic packages merely for convenience without authorization.

## Hypothesis Ledger

Maintain a compact table in the case record:

| Rank | Hypothesis | Supporting evidence | Contradicting evidence | Next safe discriminator | Status |
|---|---|---|---|---|---|

Close or demote hypotheses when evidence contradicts them. Do not keep a favored theory alive by adding unsupported exceptions.

## Change Gate

Before a change, record:

- exact target and current state;
- intended new state;
- why the change discriminates or resolves the issue;
- dependencies and blast radius;
- whether it survives reboot/redeployment;
- rollback steps and required artifacts;
- verification command and expected result;
- authorization or change reference when required.

Prefer one discriminating change at a time unless the product requires an atomic set.

## Verification

Verification should cover four layers where applicable:

1. The original user-visible symptom is gone.
2. The service/component reports healthy state.
3. Logs contain no new relevant error and show the expected transition.
4. The result persists across the relevant boundary: process restart, service restart, reboot, failover, redeployment, or scheduled run.

Package installation, a green service status, or command exit code alone is not proof that the user outcome works.

## Closeout

Record:

- concise root cause, or `Cause Not Proven` when appropriate;
- contributing conditions;
- exact corrective change;
- verification evidence;
- rollback state;
- follow-up risk or monitoring;
- reusable knowledge promoted;
- related Ansible or infrastructure-as-code change;
- wiki publication status;
- remaining `Needs Validation` items and owners.

If the action only reduced symptoms, label it a workaround and keep the cause investigation open or explicitly deferred.
