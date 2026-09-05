# syntax=docker/dockerfile:1.7

FROM alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce AS palworld_assets
RUN apk add --no-cache git && \
    git clone https://github.com/zaigie/palworld-server-tool.git /source && \
    git -C /source checkout 3b0e1e96a7500846e3a6fbac66f1c248b4c286e7

FROM python:3.14-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN python -m venv /opt/venv && pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv requirements --hash > /tmp/requirements.txt && \
    /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

FROM docker:29-cli@sha256:862099ada15c669000bef53aa4cb9d821262829f45b0dda2159ccb276443043b AS docker_cli

FROM python:3.14-alpine@sha256:26730869004e2b9c4b9ad09cab8625e81d256d1ce97e72df5520e806b1709f92 AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apk add --no-cache ca-certificates tzdata && \
    addgroup -g 1000 app && \
    adduser -D -u 1000 -G app -h /home/app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
COPY --chown=app:app manage.py ./
COPY --chown=app:app config ./config
COPY --chown=app:app gsc ./gsc
COPY --chown=app:app pals ./pals
COPY --from=palworld_assets /source/web/src/assets /opt/palworld-assets
COPY --chown=app:app docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN DJANGO_SECRET_KEY=build-only-static-key DJANGO_DEBUG=false DJANGO_SECURE_SSL_REDIRECT=false DJANGO_SECURE_COOKIES=false \
    /opt/venv/bin/python manage.py collectstatic --noinput && \
    chmod +x /usr/local/bin/docker-entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "150", "--no-control-socket", "--access-logfile", "-", "--error-logfile", "-", "config.wsgi:application"]
