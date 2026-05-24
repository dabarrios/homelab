# Port Map

Quick reference for what lives where. There is no direct internet exposure.

## Utilities Stack

| Port | Service | Notes |
| --- | --- | --- |
| `3001` | BentoPDF | PDF tools |
| `3002` | Omni Tools | General utility tools |

## Paperless Stack

| Port | Service | Notes |
| --- | --- | --- |
| `3003` | Paperless AI | AI helper for Paperless |
| `3004` | Paperless-ngx | Main Paperless web UI |

## Management Stack

| Port | Service | Notes |
| --- | --- | --- |
| `4001` | Homarr | Main dashboard / homepage |
| `4002` | Portainer | Docker management UI |

## Monitoring Stack

| Port | Service | Notes |
| --- | --- | --- |
| `4101` | Alloy | Alloy web UI / status endpoint |
| `4102` | Dashdot | System stats dashboard |
| `4103` | Grafana | Logs and dashboards |
| `4104` | Loki Gateway | Loki endpoint for log shipping/querying |
| `4105` | Uptime Kuma | Service monitoring |

## Automation Stack

| Port | Service | Notes |
| --- | --- | --- |
| `6001` | Bazarr | Subtitles |
| `6002` | Bazarr Anime | Anime subtitles |
| `6003` | Radarr | Movies |
| `6004` | Radarr Anime | Anime movies |
| `6005` | Sonarr | TV shows |
| `6006` | Sonarr Anime | Anime series |
| `6007` | Prowlarr | Indexers |

## VPN Stack

| Port | Service | Notes |
| --- | --- | --- |
| `6101` | qBittorrent | Web UI, published through Gluetun |

qBittorrent itself uses Gluetun's network namespace, so the web UI port is published on the `gluetun` service.

## Frontend Stack

| Port | Service | Notes |
| --- | --- | --- |
| `8001` | Jellyfin | Media server |
| `8002` | Jellyseerr | Media requests |

## Cloud Stack

| Port | Service | Notes |
| --- | --- | --- |
| `9001` | File Browser | Web UI |
| `9002` | Syncthing | Web UI |
| `9003/tcp` | Syncthing | TCP listening port |
| `9003/udp` | Syncthing | UDP listening port |
| `9004/udp` | Syncthing | Protocol discovery |

## Immich Stack

| Port | Service | Notes |
| --- | --- | --- |
| `9101` | Immich | Photo management |

## Nextcloud Stack

| Port | Service | Notes |
| --- | --- | --- |
| `9001` | Nextcloud AIO | AIO mastercontainer UI |
| `9002` | Nextcloud backend | Internal Apache backend port from `NEXTCLOUD_BACKEND_PORT` |

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

## Database Stack

No host ports are published.
