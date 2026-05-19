# Aspis Functional Specifications Draft

Working draft. This will probably change a lot.

## Purpose

Aspis scans Docker Compose files from a homelab repository and creates a security
posture view of the environment.

The first version should focus on static Compose analysis.

## Users

Primary user:

- Homelab owner / student / admin.

Future possible users:

- Someone reviewing a Compose repo.
- Someone preparing a homelab security report.
- Someone learning Docker hardening.

## Main Workflow

1. User gives Aspis a Compose file or directory.
2. Aspis finds Compose files.
3. Aspis parses YAML.
4. Aspis normalizes stack and service data.
5. Aspis runs scanner rules.
6. Aspis outputs findings as JSON.
7. Later, backend saves scan results.
8. Later, dashboard displays findings.
9. Later, user accepts risks or exports report.

## MVP Features

### Compose Scanner

Must read:

- stack name.
- service name.
- container name.
- image.
- ports.
- volumes.
- networks.
- environment keys.
- env files.
- restart policy.
- healthcheck.
- privileged.
- cap_add.
- devices.
- network_mode.

### Findings

A finding should include:

- rule id.
- severity.
- stack.
- service.
- title.
- description.
- evidence.
- remediation.

### Rule Ideas

Rules to start with:

- container uses `latest`.
- image has no explicit version.
- container is privileged.
- Docker socket is mounted.
- sensitive environment variable appears.
- service exposes host ports.
- important/admin service exposes host ports.
- missing healthcheck.
- container appears to run as root.
- host filesystem path is mounted.
- broad host path is mounted.
- torrent service not routed through VPN.
- service attached to too many networks.
- restart policy missing.
- database exposed unnecessarily.

### Dashboard Later

Views:

- scan summary.
- stacks.
- services.
- findings.
- rule catalog.
- accepted risks.
- reports.

## Non-Functional Requirements

- Must run locally.
- Must not require a hosted database.
- Must not modify scanned Compose files.
- Must be useful from CLI before frontend exists.
- Must redact sensitive values.

## Out Of Scope For MVP

- AI copilot.
- live Docker Engine scan.
- automatic fixes.
- PDF reports.
- cloud auth.
- multi-user enterprise features.
- Kubernetes.

## Future AI Copilot

Only after deterministic scanner works.

Possible AI features:

- explain a finding.
- summarize a scan.
- generate remediation checklist.
- compare two scan runs.
- draft GitHub issues.
- help explain project for interviews.

The AI should only use structured scan results. It should not be the scanner.

