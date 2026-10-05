# Knowledge Governance and Continuous Learning

The agent's durable memory is the reviewed repository, not the model's conversational recollection.

## Knowledge States

Use a promotion pipeline:

1. **Captured:** raw ticket observation, command output, or reporter statement.
2. **Corroborated:** supported by another source or reproducible test.
3. **Verified:** tested against a stated success condition on identified versions.
4. **Promoted:** incorporated into the canonical runbook, known issue, inventory, decision, or automation.
5. **Superseded:** retained for history but no longer active; points to its replacement.

Do not move directly from Captured to Promoted.

After a case reaches Verified, the harness may generate a review artifact without copying the full ticket:

```bash
python3 "$SKILL_ROOT/scripts/create_knowledge_candidate.py" \
  --case-record /approved/repo/tickets/CASE.md \
  --output /approved/repo/knowledge-candidates/example.md \
  --title 'Version-bounded issue title' \
  --applicability 'Exact product, OS, kernel, and hardware boundary' \
  --resolution 'Verified correction' \
  --verification 'Evidence proving the success condition' \
  --rollback 'Tested rollback or recovery action' \
  --evidence 'root:path@locator#chunk-N'
```

The generated record is always `candidate`. Repository review promotes it, after which the private index is rebuilt and representative behavioral searches are rerun. This is governed continuous learning; conversation history alone never changes active guidance.

## Promotion Criteria

A reusable entry should state:

- symptom and detection evidence;
- affected and unaffected versions/platforms;
- prerequisites and environmental assumptions;
- root cause or clearly labeled unknown cause;
- safe diagnostic sequence;
- repair and rollback;
- verification;
- source ticket/change identifiers;
- vendor references and retrieval dates;
- last verified date and owner when repository policy supports them.

## Contradictions and Drift

When new evidence contradicts existing guidance:

1. Do not overwrite history silently.
2. Mark the conflict and identify both sources and versions.
3. Test the smallest safe discriminating case.
4. Update the canonical record and mark old guidance superseded.
5. Rebuild the local knowledge catalog and private search index, then rerun the affected evaluation cases.

## Knowledge Hygiene

- Keep environment-specific values in inventory or configuration, not generic runbooks.
- Keep commands version-aware; avoid `latest` when reproducibility matters.
- Do not copy entire vendor manuals into runbooks. Cite the approved local reference and summarize the decision-relevant portion.
- Do not index secrets, protected license content, crash dumps containing credentials, or raw credential-store exports.
- Expire or review time-sensitive guidance such as support matrices, driver branches, lifecycle dates, CVEs, repository endpoints, and compatibility tables.
- Distinguish vendor support from a locally observed success that the vendor does not support.

## Catalog Use

The metadata catalog is a discovery accelerator, not a source of truth. Always open the canonical file before relying on its content. Rebuild it after material repository changes and compare its generated timestamp and roots with the current session.
