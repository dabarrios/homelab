# Production deployment

1. Copy `.env.example` to an environment file outside Git and generate a unique `DJANGO_SECRET_KEY`.
2. Set the real hostname in `DJANGO_ALLOWED_HOSTS` and HTTPS origin in `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. Terminate TLS at a trusted reverse proxy and set `DJANGO_BEHIND_HTTPS_PROXY=true`.
4. Run `python manage.py migrate` and `python manage.py collectstatic --noinput`.
5. Start Gunicorn from this directory with `pipenv run gunicorn homelab.wsgi:application --bind 127.0.0.1:8000 --workers 1`; do not use `manage.py runserver`.
6. Configure the reverse proxy to serve `staticfiles/` at `/static/`.
7. Ensure the service account can read the Compose project and access Docker, but cannot modify unrelated files.
8. Create a dedicated Django staff account with a strong password for server controls.
9. Back up `db.sqlite3` and restrict dashboard access to the private network or VPN.

Leave `DJANGO_HSTS_SECONDS=0` for the first verified HTTPS deployment. Increase it only after confirming HTTPS works correctly for the hostname.
