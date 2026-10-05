# Release and Offline-Transfer Integrity

## Public Skill Releases

Publish the portable skill only after the automated test matrix, source-registry validation, tracked-payload boundary check, secret scan, operational-data scan, and clean-clone smoke test pass.

Create an immutable semantic-version tag and a GitHub release. Attach a source archive generated from the tagged Git tree and a `SHA256SUMS` file covering that archive. Record the tag, commit ID, archive digest, test result, and release URL in the release notes.

A Git tag, GitHub TLS connection, or bare SHA-256 checksum is not by itself offline publisher authentication. If the destination requires cryptographic publisher identity, sign `SHA256SUMS` with the organization's approved release key and transfer the independently trusted public key through the approved trust-distribution process. Never create or publish an ad hoc signing key and describe it as organizational trust.

## Private Corpus Releases

Keep private corpus releases separate from public skill releases. The bundle manifest lists every source and generated artifact, its relative path, SHA-256 value, acquisition/provenance metadata, classification, and source status. Normal activation requires the detached manifest signature and the approved public-key keyring. `--allow-unsigned` is limited to an explicitly accepted development or personal exception.

On import:

1. follow the approved removable-media ingress and malware-scanning process;
2. verify the detached manifest signature with the independently trusted keyring;
3. verify every manifest checksum and reject unlisted files when the release policy requires it;
4. run `doctor.py` and a representative citation-bearing search;
5. switch the active configuration atomically and retain the previous bundle as the rollback version.

Do not publish private documents, generated indexes, credentials, license material, tickets, host captures, network details, or vendor-entitled payloads in the public GitHub release.
