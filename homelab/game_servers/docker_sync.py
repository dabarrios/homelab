"""Synchronize Compose-managed game containers into Django."""

import json
import re
import subprocess

from django.utils.text import slugify

from .models import GameServer


PROJECT_LABEL = "com.docker.compose.project=game-stack"


def _environment_map(container):
    return {
        key: value
        for item in container.get("Config", {}).get("Env", [])
        if "=" in item
        for key, value in [item.split("=", 1)]
    }


def _memory_in_gb(value):
    match = re.fullmatch(r"\s*(\d+)\s*([GMgm]?)\s*", value or "")
    if not match:
        return 1
    amount, unit = int(match.group(1)), match.group(2).upper()
    return max(1, amount if unit != "M" else round(amount / 1024))


def _minecraft_port(container):
    bindings = container.get("HostConfig", {}).get("PortBindings", {})
    published = bindings.get("25565/tcp") or []
    if not published:
        return None
    try:
        return int(published[0]["HostPort"])
    except (KeyError, TypeError, ValueError):
        return None


def _unique_slug(name):
    base = slugify(name) or "game-server"
    candidate = base
    suffix = 2
    while GameServer.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def sync_docker_game_servers():
    """Upsert game containers and return None, or an unavailable reason."""
    try:
        listed = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label={PROJECT_LABEL}", "--format", "{{.ID}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        container_ids = listed.stdout.split()
        if not container_ids:
            return None

        inspected = subprocess.run(
            ["docker", "inspect", *container_ids],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        containers = json.loads(inspected.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return str(error)

    seen_names = set()
    for container in containers:
        labels = container.get("Config", {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service", "")
        image = container.get("Config", {}).get("Image", "")
        if service.endswith("-backup") or "mc-backup" in image:
            continue

        name = container.get("Name", "").lstrip("/")
        if not name:
            continue

        seen_names.add(name)
        environment = _environment_map(container)
        defaults = {
            "game": "Minecraft" if "minecraft" in image else service.replace("-", " ").title(),
            "allocated_memory": _memory_in_gb(environment.get("MEMORY")),
            "version": environment.get("VERSION", ""),
            "port": _minecraft_port(container),
            "is_active": container.get("State", {}).get("Status") == "running",
        }
        server = GameServer.objects.filter(container_name=name).first()
        if server is None:
            defaults.update({"world_name": name.upper(), "slug": _unique_slug(name), "notes": ""})
            GameServer.objects.create(container_name=name, **defaults)
        else:
            for field, value in defaults.items():
                setattr(server, field, value)
            server.save(update_fields=[*defaults])

    GameServer.objects.filter(container_name__in=seen_names).exclude(
        container_name__in=[
            container.get("Name", "").lstrip("/")
            for container in containers
            if container.get("State", {}).get("Status") == "running"
        ]
    ).update(is_active=False)
    return None

