# Port Map

Quick reference for what lives where. There is no direct internet exposure.

## Management Stack

| Port | Service | Notes |
| --- | --- | --- |
| `4001` | Dashdot | System stats dashboard |
| `4002` | Homarr | Main dashboard / homepage |
| `4003` | Portainer | Docker management UI |
| `4004` | Uptime Kuma | Service monitoring |

## Monitoring Stack

| Port | Service | Notes |
| --- | --- | --- |
| `4501` | Grafana | Logs and dashboards |
| `4502` | Loki Gateway | Loki endpoint for log shipping/querying |
| `4503` | Alloy | Alloy web UI / status endpoint |

## Frontend Stack

| Port | Service | Notes |
| --- | --- | --- |
| `8001` | Jellyfin | Media server |
| `8002` | Jellyseerr | Media requests |

## Automation Stack

| Port | Service | Notes |
| --- | --- | --- |
| `6001` | Radarr | Movies |
| `6002` | Radarr Anime | Anime movies |
| `6003` | Sonarr | TV shows |
| `6004` | Sonarr Anime | Anime series |
| `6005` | Bazarr | Subtitles |
| `6006` | Bazarr Anime | Anime subtitles |
| `6007` | Prowlarr | Indexers |

## VPN Stack

| Port | Service | Notes |
| --- | --- | --- |
| `7001` | qBittorrent | Web UI, published through Gluetun |

qBittorrent itself uses Gluetun's network namespace, so the web UI port is published on the `gluetun` service.

## Utilities Stack

| Port | Service | Notes |
| --- | --- | --- |
| `3001` | BentoPDF | PDF tools |
| `3002` | Omni Tools | General utility tools |

## Paperless Stack

| Port | Service | Notes |
| --- | --- | --- |
| `9003` | Paperless AI | AI helper for Paperless |
| `9004` | Paperless-ngx | Main Paperless web UI |

## Immich Stack

| Port | Service | Notes |
| --- | --- | --- |
| `5001` | Immich | Photo management |

## Nextcloud Stack

| Port | Service | Notes |
| --- | --- | --- |
| `9001` | Nextcloud AIO | AIO mastercontainer UI |
| `9002` | Nextcloud backend | Internal Apache backend port from `NEXTCLOUD_BACKEND_PORT` |

Only `9001` is directly published in the compose file. `9002` is handed to Nextcloud AIO as the backend Apache port and bound to `127.0.0.1`.

## DNS Stack

| Address | Service | Notes |
| --- | --- | --- |
| `192.168.6.3` | Pi-hole | Runs on macvlan, so it gets its own LAN IP instead of normal host port mappings |

## Game Stack

| Port | Service | Notes |
| --- | --- | --- |
| `25565` | Minecraft `mc1` | Main Minecraft port |
| `24455/udp` | Minecraft `mc1` | Simple Voice Chat |
| `25566` | Minecraft `mc2` | Host port mapped to container `25565` |
| `24454/udp` | Minecraft `mc2` | Simple Voice Chat |

RCON ports are set in the Minecraft env files, but they are not published in the compose file right now.

## Drive Stack

| Port | Service | Notes |
| --- | --- | --- |
| `8081` | Filebrowser | Planned/current drive web UI port from `drive-stack/.env` |

## Database Stack

No host ports are published.
