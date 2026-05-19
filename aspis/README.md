# Aspis

Aspis is a planned self-hosted security posture dashboard for Docker-based
homelabs.

The name comes from the Greek word "aspis", meaning shield.

## Current Status

Phase 1 is planning and documentation only. No scanner, backend, frontend, or
database code has been created yet.

This folder is intentionally isolated from the existing homelab stack folders.
Aspis should eventually scan the rest of the repository, but it should not modify
the real Docker Compose files.

## Working Documents

- `docs/aspis_planning_notes.md`
- `docs/aspis_functional_specifications_draft.md`
- `docs/aspis_erd_draft.md`

These are rough planning documents. They are allowed to be a little messy...

## First Branch

```bash
feature/aspis-planning
```
