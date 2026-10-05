# Knowledge Domain Roadmap

This is the coverage map for the private troubleshooting corpus. It describes what to acquire and model; it does not claim that every item is already present.

## Priority 0: Corpus Safety and Evidence

- Source identity, version, lifecycle, retrieval date, digest, signature result, classification, handling terms, freshness, and supersession.
- Evidence states: `Observed`, `Vendor-stated`, `Inferred`, `Proposed`, `Verified`, `Needs Validation`, and `Superseded`.
- Command risk: read-only, state-changing, service-impacting, destructive, security-sensitive, privilege required, rollback, and verification.
- Compatibility as effective-dated relationships, not a single “current” value.
- Private/public separation, secret and operational-information scanning, citation correctness, and prompt-injection resistance.

## RHEL 7, 8, 9, and 10

Acquire release-specific administration, security, package, lifecycle, and troubleshooting material for each operated major and minor release. Cover:

- lifecycle, Extended Life Cycle Support and Extended Update Support boundaries, release dates, errata, advisories, and repository/channel identity;
- RPM, YUM/DNF, modularity where applicable, subscription-manager, Satellite/content views, local repositories, GPG signatures, and offline patching;
- systemd, journald, rsyslog, auditd, logrotate, process/resource management, tuned, kdump, and performance tools;
- SELinux, firewalld/nftables, crypto-policies, FIPS, OpenSCAP, STIGs, fapolicyd, USBGuard, and authentication policy;
- NetworkManager, routing, DNS, chrony/NTP/PTP, bonding/teaming, VLANs, bridges, proxying, and troubleshooting packet flow;
- boot, UEFI/Secure Boot, GRUB, dracut/initramfs, rescue, Anaconda, Kickstart, Image Builder, and Leapp boundaries;
- storage: XFS, LVM, Stratis, multipath, iSCSI, NFS, SMB, autofs, quotas, encryption, snapshots, backup, and recovery;
- identity: SSSD, realmd, Kerberos, LDAP, Samba, Active Directory, IdM/FreeIPA, certificates, and trust relationships;
- Podman/Buildah/Skopeo, KVM/libvirt, VMware integration, OpenShift clients, high availability/Pacemaker, and cloud images.

Never generalize a RHEL 7 command, package name, firewall stack, Python expectation, or support statement to RHEL 8-10 without version evidence.

## NVIDIA, CUDA, Hardware, and MATLAB

- PCI identity, GPU architecture, compute capability, firmware, GSP, PCIe topology, NUMA, power, cooling, ECC, AER/IOMMU, Xid events, and health evidence.
- Driver branch lifecycle; open versus proprietary modules; kernel/userspace exact-version matching; RHEL packaging; DNF modules/profiles/contexts; precompiled kmod versus DKMS; kABI assumptions; kernel-devel/build tool requirements.
- Secure Boot, kernel lockdown, module signatures, MOK/organization keys, nouveau and initramfs implications, device nodes, persistence daemon, udev, permissions, cgroups, and containers.
- NVIDIA RPM repository metadata, keys, package closure, internal mirroring, transfer manifests, install/rollback, and coordinated kernel/driver version locking.
- CUDA driver compatibility versus an installed CUDA Toolkit; compiler support; CUDA Compatibility packages; cuDNN; TensorRT; NCCL; Container Toolkit; Fabric Manager, NVLink/NVSwitch, MIG, vGPU, and licensing only when applicable.
- HPE platform model, BIOS/UEFI, firmware/SPP, iLO, supported slot/topology, power supplies, cooling, RAS, and vendor support matrix.
- MATLAB release, supported GPU compute capabilities and driver requirements; ordinary `gpuArray`, Parallel Computing Toolbox, and Deep Learning Toolbox versus `mexcuda`, GPU Coder, and standalone deployment; release-specific CUDA/cuDNN/TensorRT prerequisites; air-gap FlexNet context.

## Ansible and Red Hat Automation Platform

- `ansible-core` versus the community package, exact collection versions, inventory plugins, host patterns, configuration and variable precedence, connection plugins, SSH/WinRM, become, interpreter discovery, facts/caching, roles, imports/includes, handlers, blocks/rescue/always, strategies, serial/throttle/forks/async, and check/diff limits.
- Jinja, filters, lookups, tests, templates, Vault/`no_log`, idempotence, logging, performance, deprecations, and porting guides.
- Collection/role/module/plugin development, FQCNs, `ansible-test`, `ansible-lint`, Molecule, execution environments, `ansible-builder`, `ansible-navigator`, dependency locks, content signing, offline Galaxy, and private Automation Hub.
- AAP Controller, inventories, projects, credentials, job/workflow templates, surveys, schedules, RBAC, LDAP/AD/SAML, Receptor, Event-Driven Ansible, backup/restore, cluster health, and upgrades.
- Prioritize installed versions of `ansible.builtin`, `ansible.posix`, `community.general`, `community.crypto`, `ansible.windows`, `community.windows`, `microsoft.ad`, `redhat.rhel_system_roles`, and environment-specific virtualization, network, database, and container collections.

## Windows Server and Active Directory

- Windows Server 2019, 2022, and 2025 release/build lifecycle, servicing, roles/features, Server Core, PowerShell, eventing, services, storage, networking, Defender, firewall, certificates, backup, failover clustering, Hyper-V, and troubleshooting.
- AD DS forests/domains, FSMO, sites/subnets, replication, trusts, DNS, DHCP, Kerberos, NTLM boundaries, time, GPO, AD CS/PKI, LDAP signing/channel binding, gMSA, auditing, recovery, and authoritative/non-authoritative restore.
- Linux integration through SSSD, realmd, Samba, Kerberos, DNS, certificates, UID/GID mapping, sudo policy, and failure isolation.

## Jenkins

- Weekly versus LTS, exact core/Java/controller/agent compatibility, installation model, JENKINS_HOME, systemd/WAR/container/Kubernetes, reverse proxy, Remoting, nodes/labels/clouds, executors/queue/workspaces, disk/inodes, JVM/GC/thread dumps, backup/restore, quiet-down, restart, and upgrade paths.
- Declarative/Scripted Pipeline, CPS, durable tasks, multibranch, webhooks, shared-library trust and pinning, Job DSL, credentials binding, artifacts/tests/retention, locks, timeouts, retries, and supported visualization.
- JCasC, authentication/authorization, LDAP/AD, CSRF/CSP, controller isolation, agent-to-controller controls, Groovy sandbox/script approval, plugin dependencies/health/advisories, and support-bundle handling.
- Offline WAR/RPM, checksums/signatures, Plugin Installation Manager, pinned plugin dependency closure, update-center metadata, Java/core constraints, and restore-tested bundles.

Do not inherit stale generic guidance. In particular, bind Java requirements to the installed Jenkins line and treat deprecated plugins as historical unless the exact environment still uses them.

## Atlassian Data Center

- Shared platform: exact product/build/license, Java/JDK, bundled Tomcat, OS, supported database/driver/collation, connection pool, local/shared home, cluster/Hazelcast, load balancer/stickiness, reverse proxy/context path, TLS/trust stores, DNS/time, NFS, mail, LDAP/AD/SAML, Marketplace apps, Application Links, indexes/caches, backup/restore, upgrade, audit, JVM diagnostics, and support-ZIP privacy.
- Jira/JSM: projects, schemes, workflows, fields/screens, permissions/security, notifications, automation, JQL, indexes, mail, Assets, portals/queues/SLAs, knowledge-base integration, cluster state, and upgrades.
- Confluence: spaces/permissions, attachments, index, Synchrony, macros, caches, shared home, cluster, database consistency, base URL/proxy, application links, LDAP/SSO, backup/restore, and upgrades.
- Bitbucket: supported Git, repository storage, shared home, Mesh, mirrors, search, LFS, hooks, pull requests, branch permissions, webhooks, PATs/SSH keys, signing, cluster/database, Jenkins/Jira integration, REST API, and hybrid licensing.
- Bamboo, Crowd, Fisheye, and Crucible only when deployed, including their retirement and migration paths.
- Track product lifecycle and Data Center end-of-life announcements as effective-dated facts. Refresh them before upgrade or procurement decisions.

## Development, DevOps, and Common Dependencies

- Git internals/recovery; GitHub, GitLab, Forgejo, and Bitbucket workflows; branching, reviews, signing, and release provenance.
- Bash, PowerShell, Python, Java/Groovy, REST/HTTP, JSON/YAML/XML, SQL, testing, debugging, profiling, and secure coding.
- Maven, Gradle, npm, pip, NuGet, Go modules, Nexus, Artifactory, SonarQube, registries, dependency locking, SBOM/SPDX/CycloneDX, SLSA, signing, scanning, and offline mirrors.
- Podman, Docker, Kubernetes, OpenShift, Helm, Argo CD/GitOps, Terraform/OpenTofu, Packer, and Vault.
- PostgreSQL, Oracle, SQL Server, and MySQL; Apache HTTP Server, NGINX, HAProxy, DNS, NTP, SMTP, TLS/PKI, storage, and load balancing.
- Prometheus, Grafana, Elastic/OpenSearch, Loki, OpenTelemetry, Wazuh, Splunk when deployed, alerting/on-call, backup/restore, business continuity, and disaster recovery.

## Teaching Standard

For every reviewed troubleshooting procedure, explain:

1. What the subsystem is and why it exists.
2. Where it sits in the architecture.
3. Which evidence to collect first.
4. What each command tests.
5. How likely outputs support or reject a hypothesis.
6. Which action changes state and its blast radius.
7. Preconditions, persistence/reboot boundaries, rollback, and verification.
8. What should be recorded and when to escalate.

Use the simplest explanation first, then introduce the precise product vocabulary. A command list without interpretation is not a complete troubleshooting article.
