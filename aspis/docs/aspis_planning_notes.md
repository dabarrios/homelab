# Aspis Planning Notes

This is the messy working doc. It is not supposed to read like final product
documentation yet.

## Name

Aspis.

Greek word for shield. Good fit because the project is about defensive visibility
for a homelab.

Possible subtitle:

Self-hosted security posture dashboard for Docker homelabs.

## What This Is

A practical scanner/dashboard for my actual homelab repository.

It should look at Docker Compose files and answer:

- What services am I running?
- What ports are exposed?
- Which services have risky mounts?
- Which services are using `latest`?
- Which services have Docker socket access?
- Which services are privileged?
- Which services are missing healthchecks?
- Which risks are intentional?

## What This Is Not

Not an AI chatbot.

Not a generic vulnerability scanner at first.

Not a thing that automatically edits my real Compose files.

Not a SaaS app.

Not a Kubernetes project.

## Why I Want To Build It

My homelab has grown naturally over time. That is good for learning, but it means
the security picture is spread across a bunch of Compose files.

This project gives me something useful and portfolio-worthy:

- Docker.
- Linux.
- self-hosting.
- networking.
- risk analysis.
- full-stack app development.
- cybersecurity thinking.
- real examples from my own environment.

## Repo Reality

The current homelab repo has separate stack folders:

- `vpn-stack`
- `frontend-stack`
- `automation-stack`
- `dns-stack`
- `immich-stack`
- `paperless-stack`
- `management-stack`
- `monitoring-stack`
- `nextcloud-stack`
- `game-stack`
- `database-stack`
- `utilities-stack`

Common pattern: most stacks use external `home-net`.

Things that Aspis should definitely notice:

- `latest` image tags.
- host ports using `${VAR:-default}`.
- Docker socket mounts.
- privileged containers.
- host mounts like `/`.
- admin dashboards exposed on host ports.
- databases should usually not publish ports.
- qBittorrent should route through Gluetun.
- Pi-hole uses macvlan and LAN IP behavior.
- Grafana has anonymous admin enabled in monitoring stack.

## MVP Thought

The scanner should be useful before there is a dashboard.

First useful thing:

```bash
aspis scan ../frontend-stack/docker-compose.yml --json
```

Output should be finding objects.

Then scan a whole folder:

```bash
aspis scan .. --json
```

## Phase Thinking

Phase 1: planning docs only.

Phase 2: scanner CLI. Parse one Compose file. Detect `latest`.

Phase 3: more scanner rules.

Phase 4: FastAPI.

Phase 5: database.

Phase 6: React dashboard.

Phase 7: accepted risks and Markdown reports.

Phase 8: Dockerized deployment.

Phase 9: polish.

Phase 10: optional AI copilot, but only after the real scanner exists.

## First Branch

`feature/aspis-planning`

This branch should probably only contain:

- README.
- planning notes.
- functional spec draft.
- ERD draft.

No code yet.

## Open Questions

- Should the first dashboard show stacks first or findings first?
- Should accepted risks attach to exact findings or rule/service pairs?
- Should scanner store raw Compose JSON in the DB?
- Should rules live in Python files, YAML files, or both?
- How much should Aspis know about my specific homelab expectations?
- Should "expected VPN route" be a configurable rule?
- Should the scanner treat `${VAR}` values as unknown, safe, or suspicious?

