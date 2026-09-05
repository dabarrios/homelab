# Container deployment

The dashboard runs as a non-root Gunicorn container built from a multi-stage Alpine image.

## First deployment

1. Copy `.env.example` to `.env` and generate a unique `DJANGO_SECRET_KEY`.
2. Set the real hostname in `DJANGO_ALLOWED_HOSTS` and HTTPS origin in `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. Set `DOCKER_GID` using `stat -c %g /var/run/docker.sock`.
4. Ensure `data/db.sqlite3` exists. The current database has already been copied there.
5. Build and start with `docker compose up -d --build` from the `django/` directory.
6. Inspect startup with `docker compose logs -f dashboard`.
7. Verify health with `docker compose ps`.

Migrations run automatically on every container start. Static assets are compressed and baked into the image during the build.

## HTTPS

Place the dashboard behind a trusted HTTPS reverse proxy. Keep the published port private, set `DJANGO_BEHIND_HTTPS_PROXY=true`, and configure secure cookies and redirects only after HTTPS is working.

Leave `DJANGO_HSTS_SECONDS=0` for the first verified HTTPS deployment. Increase it only after confirming the hostname always works over HTTPS.

## Docker access

The Docker socket grants powerful host access. The application only exposes staff-authenticated, allowlisted start and stop actions, but the dashboard must remain restricted to the private network or VPN.

## Palworld live-save sync

Set `PALWORLD_LIVE_SAVE_HOST_DIR` in `.env` to the host directory containing `Level.sav` and `Players/`. Compose mounts that directory read-only at `/palworld-save`. The dashboard never decodes files in place; it copies them to `./data/pals/decode-work`.

Docker deployments use the pinned native parser sidecar automatically. Direct Windows development keeps the existing WSL workflow and may continue using `PALWORLD_LIVE_SAVE_DIR` and `PALWORLD_PARSER_TOOLS_DIR` with Windows drive-letter paths. Set `PALWORLD_PARSER_RUNTIME=wsl` to force it.
