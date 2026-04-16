# Homelab

This repository contains the Docker Compose stacks and configs for my personal homelab.

I originally set this up just to run Jellyfin, but it kept growing as I added more services and learned more along the way. Now it includes things like container management, VPN routing, DNS, monitoring, storage separation, and a few other self-hosted apps.

## Environment

- **Host OS:** Ubuntu Server
- **Container Platform:** Docker Compose
- **Remote Access:** Tailscale
- **Service Management:** systemd + Docker
- **Storage Layout:** Separate drives for OS, application data, media, game servers, and backups

## Repository Layout

Services are split into separate stacks by function instead of being placed in one large Compose file. This keeps the setup easier to maintain, troubleshoot, and expand over time.

### Management Stack
Tools I use to keep track of everything and make sure things are running properly:

- **Portainer** – manage containers, check logs, restart stuff when needed
- **Homarr** – dashboard to access all my services in one place
- **Uptime Kuma** – monitors services and alerts me if something goes down
- **Dashdot** – shows system stats like CPU, RAM, etc.
- **Watchtower** – handles automatic container updates

### Frontend Stack
This is what I actually use day-to-day for media:

- **Jellyfin** – media server for watching everything
- **Jellyseerr** – lets me request movies/shows and ties into the automation

### Automation Stack
This is what handles grabbing, organizing, and keeping media up to date:

- **Sonarr** / **Sonarr Anime** – manages TV shows
- **Radarr** / **Radarr Anime** – manages movies
- **Bazarr** / **Bazarr Anime** – handles subtitles
- **Prowlarr** – manages indexers
- **Flaresolverr** – helps bypass some site protections
- **Recyclarr** – keeps quality profiles and settings in sync

### VPN Stack
This is how I keep download traffic separate from the rest of the system:

- **Gluetun** – acts as the VPN gateway
- **qBittorrent** – runs through Gluetun instead of directly on the host

### DNS Stack
Handles DNS and basic ad blocking on my network:

- **Pi-hole** – blocks ads and trackers

Pi-hole runs on a `macvlan` network so it shows up on my LAN like its own device with a separate IP.

### Immich Stack
Self-hosted photo management:

- **Immich**
- **PostgreSQL**
- **Redis**
- **Machine Learning service**

### Nextcloud Stack
Used for file syncing and cloud-style storage:

- **Nextcloud AIO**

### Utilities Stack
A few extra tools I use outside of the main setup:

- **Paperless-ngx** – document storage and organization
- **Omni Tools** – small utility tools
- **BentoPDF** – simple PDF tools

### Game Stack
Where I run my Minecraft servers:

- Multiple **Minecraft** server instances
- Automated backups using **itzg/mc-backup**

### Database Stack
Just a basic database I keep around for testing:

- **MySQL**

## Networking Notes

Most services are connected through a shared Docker network so they can talk to each other easily. I only break things out into separate networks when there’s a reason to.

- **macvlan** – used for services that need their own IP on the LAN (like Pi-hole)
- **Tailscale** – handles remote access
- No direct port forwarding for internal services unless needed

## Why I Keep This Project

This lab gives me a place to try things out, break stuff, and fix it. It’s been one of the best ways for me to actually learn Linux, Docker, and networking outside of school.