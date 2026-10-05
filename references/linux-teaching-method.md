# Linux Teaching Method

Use this reference whenever the ticket, explanation, or runbook involves Linux administration. The aim is to solve the immediate problem while building a reusable mental model for the operator.

## Teaching Shape

For each substantive concept, use only as much of this sequence as the situation needs:

1. **Plain-English model:** describe the component or failure in one accessible sentence.
2. **Real vocabulary:** immediately name the actual service, subsystem, file, package, command, and log source.
3. **Reason it exists:** briefly explain the problem the component solves when that helps the diagnosis.
4. **Evidence commands:** introduce no more than three to five commands at once and explain each before it is run.
5. **Interpretation:** state what important outputs mean and which hypothesis each result supports or rejects.
6. **Verification:** test the user-visible outcome, service state, logs, and relevant restart or reboot boundary.
7. **Anchor:** summarize the pattern the operator should recognize next time.
8. **Check:** after a substantive explanation, ask one short comprehension question unless the user requested only a direct fix or incident urgency makes it inappropriate.

Use analogies only as a bridge. Always attach the correct technical name so the operator learns language that appears in man pages, logs, vendor documentation, and tickets.

## Diagnostic Funnel

Work down this funnel instead of guessing or immediately changing configuration:

1. **Identity and change:** exact OS release, kernel, package/application version, hardware, role, time of failure, and recent changes.
2. **State:** service, unit, process, mount, interface, device, or package state.
3. **Logs:** relevant journal slice and application logs around the failure time.
4. **Configuration:** use the application's native syntax or configuration validator when one exists.
5. **Dependencies and reachability:** sockets, ports, DNS, routes, remote services, mounts, repositories, and credentials boundaries.
6. **Security controls:** ownership and mode, SELinux labels/booleans/AVCs, firewalld or nftables, crypto policy, Secure Boot, and policy enforcement.
7. **Resources:** filesystem space and inodes, memory, OOM evidence, CPU pressure, file descriptors, and device health.
8. **Persistence:** enablement, configuration source, initramfs, bootloader, fstab, automation, and what survives a restart or reboot.

The funnel is a decision tree, not a command dump. Stop when evidence identifies the failing layer, then use the narrowest safe discriminator for the remaining hypotheses.

## Command Explanation Card

For a command that matters to the diagnosis, teach these fields in compact prose or a small table:

- **Purpose:** the question this command answers.
- **Command:** the exact command, with placeholders identified.
- **Safety:** read-only or state-changing; required privileges; affected scope.
- **Expected evidence:** the fields or lines that matter, including healthy and unhealthy examples when useful.
- **Interpretation:** what each meaningful result supports or rules out.
- **Next decision:** what to inspect or change based on the result.
- **Rollback:** required for a state-changing command.

Do not say only “run this.” Do not treat a zero exit code as proof that the user's outcome works.

## RHEL Version Discipline

- Capture `/etc/redhat-release`, `uname -r`, and the relevant RPM NEVRAs before giving version-sensitive advice.
- Default to RHEL commands only after the affected release is established.
- Label differences among RHEL 7, 8, 9, and 10. Do not assume DNF modules, repository layout, crypto policy, network stack, kernel packaging, or third-party driver packaging are identical.
- Distinguish the running kernel from installed kernels and the enabled repository view from installed package provenance.
- For another distribution, translate explicitly rather than presenting the RHEL command as universal.
- Separate ordinary administration from STIG, FIPS, RMF, or site-policy requirements. A technically functional setting is not automatically an approved setting.

## Documentation Habits

Teach the operator how to verify advice locally:

- use the exact man-page section when ambiguity matters, such as `man 5` for a file format and `man 8` for an administrative command;
- use `--help`, `systemctl help`, package documentation under `/usr/share/doc`, and vendor documentation included in the private corpus;
- record the exact product and RHEL versions to which a procedure applies;
- preserve source citations and distinguish observed output from vendor-stated behavior and inference.

## Incident Pacing

During an active outage, recovery and evidence preservation come first. Explain critical risks before commands, keep instruction notes short, and give the fuller mental model after service is restored and verified. When the user explicitly asks for a lesson, slow down, let the user predict the next diagnostic rung, and prefer safe hands-on observation or a disposable test system for destructive examples.

End the debrief with:

1. the failed layer;
2. the evidence that proved it;
3. why the correction worked;
4. how to detect recurrence;
5. one short check question.
