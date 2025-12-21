# Homelab

This repository documents my personal homelab — a project I built and continue to maintain to better understand Linux systems, Docker, networking, and self-hosted services.

What started as “I want to try Jellyfin” slowly turned into a full setup involving automation, VPN routing, DNS, monitoring, and persistent storage. Every service here exists because it solved a real problem I ran into along the way.

---

## Environment

- **Host OS:** Ubuntu Server
- **Container Platform:** Docker + Docker Compose
- **Service Control:** systemd
- **Remote Access:** Tailscale
- **Storage:** Multiple SSDs/HDDs separated by purpose (OS, services, game servers, backups)

---

## Service Layout

Services are grouped by **function** instead of being placed into a single compose file. This keeps things easier to manage and troubleshoot.

---

### Management Stack

Tools I use to keep track of what is running and to troubleshoot issues

- **Portainer** – Inspect containers, logs, volumes, and restart services
- **Homarr** – Central dashboard for quick access to services
- **Uptime Kuma** – Basic uptime monitoring and e-mail alerts

---

### Media & Automation Stack

This is where most of the learning happened.

- **Jellyfin** – Media server
- **Sonarr / Radarr** – Automated TV and movie management
- **Prowlarr** – Indexer management
- **Bazarr** – Subtitle automation
- **qBittorrent** – Download client

Download traffic is routed through a VPN container instead of running a VPN on the host.

---

### VPN Stack

- **Gluetun** – VPN gateway for qBittorrent

---

### DNS Stack

- **Pi-hole** – Network-wide ad and tracker blocking

Runs on a macvlan network so it has its own LAN IP and behaves like a normal network device.

---

### Immich Stack (Photos)

- **Immich**
- **PostgreSQL**
- **Redis**
- **Machine learning service**

This setup gave me hands-on experience working with multi-container apps that rely on databases and internal networking.

---

## Networking Setup

- Custom Docker bridge networks for service isolation
- macvlan used only when LAN visibility is needed
- No public port forwarding
- Remote access handled through Tailscale

---

## Why I Keep This Project

This lab gives me a place to experiment, break things, and fix them in a realistic environment. It’s been one of the most practical ways I’ve learned infrastructure concepts outside of school and work.
