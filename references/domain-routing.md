# Domain Evidence Router

Read the section matching the ticket. These are evidence requirements and decision boundaries, not generic repair recipes.

## NVIDIA GPUs on RHEL 8/9/10

Load the decision model and source families in [nvidia-rhel-matlab-seed-context.md](nvidia-rhel-matlab-seed-context.md). Treat it as a router, not as a substitute for a fresh vendor-repository inventory or the production host facts.

Capture before recommending a driver action:

- `lspci -Dnn` GPU identity and physical count;
- OS release, architecture, running and installed kernels;
- Secure Boot and kernel-lockdown state;
- driver branch, exact version, Open versus proprietary flavor;
- module path, signer, license, vermagic, and loaded modules;
- RPM NEVRA, DNF module stream/profile/context, repository provenance, and signature result;
- precompiled kmod versus DKMS and exact matching `kernel-devel` availability;
- `nvidia-smi` inventory, health, topology, persistence, and relevant Xid errors;
- application requirement: driver-only, system CUDA Toolkit, containers, or code generation.

Do not equate the CUDA version displayed by `nvidia-smi` with an installed CUDA Toolkit. Do not mix kernel module and userspace driver versions. Do not use a proprietary precompiled kmod when the hardware or approved design requires Open modules. Prefer distribution RPMs and modular metadata over the `.run` installer.

Separate the RHEL-major packaging paths. RHEL 8/9 Open drivers commonly use the branch-specific Open DKMS stream, while RHEL 10 may use Red Hat-signed precompiled Open modules from the Extensions repository for supported combinations. A proprietary RHEL 8/9 precompiled-status record is not evidence of Open-module coverage.

For MATLAB, distinguish ordinary GPU execution from GPU Coder/standalone builds before adding CUDA, cuDNN, or TensorRT.

Useful local search terms: GPU PCI ID, exact kernel string, driver NEVRA, `open-dkms`, `kmod-nvidia`, `nvidia-driver-cuda`, `Secure Boot`, Xid number, MATLAB release.

## RHEL and General Linux

Search the governed MD CODE RED corpus according to [code-red-corpus.md](code-red-corpus.md) before relying on generic memory. Keep its curated records, host captures, raw source material, and mined candidates at their documented trust levels.

Capture exact release and kernel, package provenance, enabled repositories, service unit and drop-ins, configuration source, SELinux mode/denials, firewall zone/rules, time synchronization, DNS, storage/mount state, resource pressure, and scoped journal evidence.

Respect RHEL 7/8/9/10 major-version differences. Avoid copying RPMs, module streams, DNF behavior, firewall assumptions, Python expectations, kernel assumptions, or remediation commands across major releases without vendor confirmation.

For package issues, preserve NEVRA, module stream/context, GPG result, dependency solver output, and repository ID. For service issues, inspect the unit plus drop-ins and effective configuration rather than only the primary file.

## Windows Server and Active Directory

Capture Windows Server edition, build, installed cumulative update, roles/features, reboot state, and whether the host is a domain controller, member server, cluster node, certificate authority, or application server.

For AD-related issues, establish DNS resolution, authoritative DNS zones, time skew, secure channel, site/subnet mapping, replication status, FSMO ownership, SYSVOL/NETLOGON health, Kerberos/SPN evidence, GPO result, certificate chain, and relevant event channels.

Prefer targeted read-only diagnostics before actions such as metadata cleanup, password reset, machine-account reset, DNS record deletion, replication forcing, role transfer/seizure, or broad cache clearing. State blast radius and recovery prerequisites for those actions.

Useful local search terms: event ID, HRESULT/Win32 error, KB number, OS build, AD site, replication partner, SPN, GPO GUID, certificate thumbprint without private-key material.

## MATLAB 2026 and GPU Workloads

Capture the exact release (`R2026a` versus `R2026b`), installed products (`ver`), add-ons, license model, GPU table, driver version, code/build location, compiler configuration, and whether the workload uses:

- ordinary `gpuArray` or Deep Learning Toolbox execution;
- `mexcuda` or custom PTX/CUDA kernels;
- GPU Coder MEX generation;
- standalone library/executable generation;
- explicit cuDNN or TensorRT targets.

Do not infer an external CUDA Toolkit requirement merely because MATLAB reports a CUDA capability or CUDA packages happen to be installed. Use release-specific archived MathWorks documentation.

## Jenkins

Capture controller and agent versions, Java versions, OS, job type, pipeline/Jenkinsfile source, shared-library revision, plugin short names and versions, node labels, executor state, failing stage, console log boundaries, and recent configuration/plugin changes.

Treat credential bindings and masked values as secrets. Never expand masked variables for diagnosis. Prefer reproduction in a non-production job or replay only when authorized. Check whether configuration is managed by JCasC or another source before editing through the UI.

Bind Java requirements to the exact Jenkins core/LTS line and check controller, agent, and CLI compatibility separately. Resolve complete plugin dependencies and security advisories for an offline plugin bundle. Do not promote a deprecated plugin as a current default merely because it appears in an older skill or installation.

## Atlassian Data Center

Capture the exact product, version/build, license state, Java/JDK, bundled application server, OS, database/driver/collation, local and shared home, node identity, cluster membership, load balancer/stickiness, proxy/context path, TLS and Java trust stores, DNS/time, NFS/shared storage, directory/SSO, Marketplace app versions, Application Links, index/cache state, and recent changes.

Use product/version-specific supported-platform, upgrade, security, and end-of-support documentation. Treat support ZIPs, logs, heap/thread dumps, database exports, and directory-sync evidence as private even when a vendor tool masks some secrets.

For Jira/JSM, add schemes/workflows/permissions/index/mail/Assets/portal evidence. For Confluence, add attachments, Synchrony, index, cache, and space-permission evidence. For Bitbucket, add Git version, shared repository storage, Mesh/mirrors/LFS/hooks, SSH/PAT/signing, and pull-request integration evidence. Add Bamboo, Crowd, Fisheye, and Crucible only when deployed, with their separate lifecycle and migration context.

## Ansible

Use the Ansible module and CLI material in MD CODE RED as offline reference context, then verify behavior against the exact `ansible-core`, collection, execution-environment, and module versions used by the affected automation repository.

Capture `ansible-core`/Automation Platform version, execution environment or Python interpreter, inventory source, applicable host/group variables, collection versions, role/playbook revision, `ansible.cfg`, privilege escalation, vault boundary, and the exact task result.

Use `--syntax-check`, `ansible-lint`, inventory inspection, and check/diff mode when they are valid for the modules involved. Check mode is not proof of safety or idempotency. Never display decrypted vault content. Convert verified repeatable manual repair into automation only with deployment authorization and a rollback/test plan.

## Cross-Platform Integration

When Linux, Windows, appliances, or applications interact, establish the full path:

- source identity and address;
- destination identity and address;
- DNS direction and record source;
- protocol, port, TLS/certificate, authentication mechanism, and time dependency;
- intermediate firewall, proxy, load balancer, NAT, VPN, or inspection point;
- server-side and client-side logs for the same timestamp;
- ownership and configuration source for each hop.

Do not treat a successful ping as proof that an application protocol, authentication, or authorization path works.
