# NVIDIA, RHEL, CUDA, and MATLAB Knowledge Router

Status: portable domain guide
Fact freshness: verify against the imported private vendor bundle before a production decision

This reference defines the questions and source families for NVIDIA GPU troubleshooting on RHEL 8, 9, and 10 and for MATLAB integration. It contains no customer topology, server model, GPU count, internal repository location, or assumed target kernel. Store those facts in the private environment overlay.

## Start With Live Identity

Collect read-only evidence before selecting a driver or package set:

```bash
cat /etc/redhat-release
uname -r
uname -m
rpm -q kernel-core kernel kernel-devel 2>/dev/null
lspci -Dnn | grep -i nvidia
mokutil --sb-state 2>/dev/null || true
cat /sys/kernel/security/lockdown 2>/dev/null || true
dnf module list nvidia-driver 2>/dev/null || true
```

When a driver is installed, also collect:

```bash
nvidia-smi -L
nvidia-smi
cat /proc/driver/nvidia/version
modinfo nvidia | egrep '^(version|license|vermagic|signer|filename):'
rpm -qa | grep -Ei '^(nvidia|kmod-nvidia|libnvidia|cuda-drivers|dnf-plugin-nvidia)|cuda|cudnn|tensorrt' | sort
dkms status 2>/dev/null || true
```

Record exact output in the private ticket/evidence layer. Do not put real host output in a public fixture.

## Driver Decision Model

Resolve all of these dimensions together:

1. GPU PCI identity, architecture, compute capability, and whether NVIDIA requires or recommends Open GPU Kernel Modules for that device generation.
2. RHEL major/minor release, architecture, running kernel, every installed/bootable kernel, and lifecycle state.
3. Secure Boot, kernel lockdown, accepted module-signing key, and organizational key-enrollment process.
4. NVIDIA branch and exact driver version.
5. Open versus proprietary kernel module flavor.
6. Precompiled kernel-specific kmod versus DKMS.
7. Exact kernel-module/userspace package match, DNF module stream/profile/context where used, and package-repository provenance.
8. Whether the workload needs only the driver or also a system CUDA Toolkit and libraries.

Blackwell and later GPU generations require NVIDIA Open GPU Kernel Modules. Never substitute a proprietary precompiled kmod for an Open-only GPU. Never substitute DKMS merely because a precompiled kmod is missing without explicitly accepting its compiler, exact `kernel-devel`, signing, baseline, and operational consequences.

## RHEL-Specific Packaging

- On RHEL 8 and RHEL 9, verify the official branch-specific Open DKMS stream, such as `nvidia-driver:580-open` when that branch is in scope. The public precompiled status trees primarily track proprietary `kmod-nvidia` packages; they do not prove precompiled Open coverage.
- On RHEL 10, verify the current NVIDIA/Red Hat documented package path separately. Red Hat-signed precompiled Open kernel modules may be supplied through the RHEL 10 Extensions repository for supported kernel/package pairs.
- Do not transpose RHEL 10 package procedures to RHEL 8/9, or treat a proprietary precompiled record as evidence for an Open-only GPU.
- If “precompiled Open only, no DKMS” is a hard requirement, report any unsupported RHEL/kernel combination as an architectural gap.

## Precompiled kmod and DKMS

A precompiled kmod is built for a specific kernel or a vendor-defined kernel ABI range. Its package naming and status page must be checked for the exact RHEL/kernel/driver/flavor combination.

DKMS compiles the kernel module locally. At minimum, verify:

- `kernel-devel` exactly matches the target kernel;
- the complete compiler/build dependency closure is available from approved repositories;
- the selected GCC/toolchain is supported;
- Secure Boot signing and key enrollment are approved and repeatable;
- compilation artifacts and logs are retained for change evidence;
- every bootable kernel that must support the GPU has a successfully built, signed, loadable module.

Do not fall back to an NVIDIA `.run` installer on an RPM-managed RHEL server unless a separately approved, vendor-supported design explicitly requires it. It bypasses normal repository/package lifecycle controls.

## Repository and Air-Gap Evidence

For each RHEL major version in scope, import the corresponding NVIDIA RPM repository metadata, GPG key, package set, release notes, installation guide, and precompiled-driver status information. Preserve:

- original `repomd.xml`, metadata, module data, and detached signatures when supplied;
- every selected RPM with NEVRA, SHA-256, `rpm -K` result, signer/key identity, and dependency closure;
- driver branch/version, module flavor, supported kernel mapping, and acquisition timestamp;
- gaps where no accepted Open precompiled kmod exists;
- the BaseOS/AppStream/EPEL dependency boundary;
- install, rollback, kernel lock, and coordinated update instructions.

Never use a “newest only” mirror policy for a repository meant to support multiple installed kernels or driver versions. Preserve all module stream versions and contexts required by the selected packages. Do not make `module_hotfixes=1` a default; it is a break-glass diagnostic bypass, not a repair for missing modular metadata.

## Driver, CUDA Toolkit, and `nvidia-smi`

The NVIDIA driver is required for GPU access. The CUDA Toolkit is a separate development stack. `nvidia-smi` showing “CUDA Version” indicates the highest CUDA driver API level supported by that driver; it does not prove `nvcc` or a system CUDA Toolkit is installed.

For applications that bundle their own user-space runtime, the driver may be sufficient. Install a system toolkit only when a workload actually compiles CUDA code or requires external CUDA libraries. Tie every toolkit, host compiler, cuDNN, TensorRT, NCCL, and compatibility package to an exact application release and supported matrix.

## MATLAB Decision Model

Capture from MATLAB when the application owner permits:

```matlab
version("-release")
ver
gpuDeviceTable
gpuDevice(1)
```

Then classify the workload:

- **Ordinary GPU execution:** `gpuArray`, Parallel Computing Toolbox, and Deep Learning Toolbox ordinarily use MATLAB-supplied CUDA runtime components. The external system requirement is normally a supported NVIDIA driver. Deep Learning Toolbox GPU work also depends on Parallel Computing Toolbox.
- **CUDA-enabled MEX in the supported MATLAB workflow:** do not assume a separately installed toolkit is required merely to run MATLAB GPU functions or generate supported CUDA-enabled MEX functions. Verify the exact release documentation.
- **Custom external toolchain or libraries:** an external CUDA Toolkit can become relevant for external libraries, custom compiler/toolchain integration, unsupported combinations, or PTX/CUDAKernel workflows.
- **GPU Coder or standalone deployment:** use the exact release-specific CUDA Toolkit, cuDNN, TensorRT, driver, compiler, and deployment matrix.

Use archived documentation for the exact MATLAB release. Do not use a current page to infer an older release's CUDA, cuDNN, TensorRT, compiler, driver, or compute-capability requirements. Current vendor information distinguishes R2026a from R2026b, so never guess one release from the other. Do not enable CUDA forward compatibility when MathWorks natively supports the GPU/release combination unless exact-release documentation directs it.

Air-gapped MATLAB licensing is a separate deployment concern: use an approved license file or reachable internal FlexNet license service. Do not store license files, File Installation Keys, or credentials in the general knowledge corpus.

## Vendor Source Families

Acquire and version these primary sources:

- NVIDIA Driver Installation Guide, Open GPU Kernel Modules guidance, branch release notes, data-center driver lifecycle, CUDA Compatibility documentation, CUDA Toolkit release notes, security bulletins, and the exact RHEL 8/9/10 repository indexes and precompiled status pages.
- Red Hat release/lifecycle documentation, kernel/package errata, DNF/modularity administration, Secure Boot/kernel signing, kABI policy, SELinux, and repository-management guidance for the exact release.
- MathWorks archived release-specific GPU Computing Requirements, Parallel Computing Toolbox documentation, Deep Learning Toolbox documentation, GPU Coder prerequisite tables, supported compilers, release notes, and licensing/install guidance.
- Hardware-vendor service manuals, slot/population rules, BIOS/UEFI settings, firmware bundles, thermal/power requirements, and supported option matrices for the exact server and GPU SKU.

The starter source registry is [source-registry.json](source-registry.json). The registry is an acquisition map, not proof that a private bundle contains the source. Coverage must be generated from the bundle manifest.

## Troubleshooting Funnel

Use this order:

1. Confirm PCI visibility and expected device count.
2. Confirm OS, kernel, Secure Boot/lockdown, and installed package provenance.
3. Confirm the correct module file, flavor, version, vermagic, signer, load state, and kernel logs.
4. Confirm `/dev/nvidia*`, persistence service, permissions, cgroups/container mapping, and process ownership.
5. Confirm kernel/userspace library version alignment and dynamic-loader paths.
6. Interpret `nvidia-smi`, Xid, AER/IOMMU, ECC, power, thermal, and GSP evidence.
7. Test the application boundary only after the base driver is healthy.
8. For MATLAB, separate driver detection from toolkit/compiler/code-generation failures.

For every proposed repair, document affected kernels, reboot boundary, rollback package set, kernel selection/locking, and post-reboot verification.

## Production Decision Gate

Do not approve an install plan until the private case record contains:

- exact hardware and PCI IDs;
- RHEL release, architecture, running and installed kernels;
- Secure Boot/lockdown and approved signing method;
- required NVIDIA branch/flavor and exact package version;
- accepted precompiled-kmod or DKMS path for every supported kernel;
- dependency closure from approved repositories;
- exact application workload boundary;
- verified source hashes/signatures and transfer evidence;
- rollback, reboot, verification, and coordinated kernel/driver update cycle.

If any selected kernel has no accepted module path, record a `GAP`. Do not conceal the gap by changing flavor or installation method without approval.
