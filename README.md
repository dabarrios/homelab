# Homelab

This repo is for my personal homelab setup.

It started as a place to run Jellyfin, then slowly grew into a bunch of Docker Compose stacks for media, monitoring, DNS, VPN-routed downloads, game servers, and other self-hosted tools.

This is mostly here so I can keep the setup organized and remember how things are wired together without losing track of what changes I make.

## Setup

- **Host OS:** Ubuntu Server
- **Containers:** Docker Compose
- **Remote access:** Tailscale on the host
- **Service management:** systemd + Docker
- **Storage:** Separate drives for the OS, app data, media, game servers, and backups

## Repo Layout

Each folder is a separate stack and serves a different goal:

- `management-stack/` - dashboards, monitoring, and container management
- `frontend-stack/` - day-to-day media apps like Jellyfin and Jellyseerr
- `automation-stack/` - Sonarr, Radarr, Bazarr, Prowlarr, and related media automation
- `vpn-stack/` - Gluetun and qBittorrent for VPN-routed downloads
- `dns-stack/` - Pi-hole and local DNS-related setup
- `game-stack/` - Minecraft servers and backups
- `database-stack/` - database containers used for testing or small projects
- `paperless-stack/` - document storage
- `immich-stack/` - photo management
- `cloud-stack/` - cloud/storage-style services
- `monitoring-stack/` - monitoring tools and configs
- `utilities-stack/` - small helper services
- `scripts/` - helper scripts
- `homelab/` - Django app for homelab/game server pages

## Environment Configuration

Most Compose stacks use one consolidated root `.env` file. Individual stack directories contain no environment files, and each stack keeps a single `docker-compose.yml`.

For a new checkout:

1. Copy `.env.example` to `.env`.
2. Fill in the real secrets and host-specific values.
3. Restrict it with `chmod 600 .env`.
4. Transfer `.env` between trusted machines using an encrypted channel such as `scp`, `sftp`, or a password manager; never commit it.

Because Docker Compose only auto-loads `.env` from the working directory, pass the shared root file when running a stack:

```bash
cd automation-stack
docker compose --env-file ../.env up -d
```

`homelab`, `aspis`, and nested application-managed files such as `paperless-stack/paperless-ai/.env` remain independent.

## Django App

The `homelab/` folder is a Django app I am building as part of this repo.

Right now it is focused on homelab and game server pages, but the goal is to keep expanding it into a more complete Django project. I am using it as a practical way to learn patterns that show up in large-scale Django applications.

As it grows, the goal is to include more structured views, templates, static files, forms, models, permissions, and helper logic instead of only simple pages.

## Networking Notes

Most services share Docker networks so they can talk to each other when needed.

- Pi-hole uses `macvlan` so it can have its own LAN IP.
- Tailscale runs on the host, not in Docker.
- Internal services are not port-forwarded unless there is a real reason.

For port mappings, see [PORTS.md](PORTS.md).

## Purpose

This is my place to learn Linux, Docker, networking, and self-hosting by actually running stuff. It is also a sandbox to break things, fix them, and reinforce my understanding.
