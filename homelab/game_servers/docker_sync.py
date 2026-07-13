"""Synchronize Compose-defined game servers and their live Docker state."""

import json
import os
import re
import subprocess
from pathlib import Path

from django.utils.text import slugify

from .models import GameServer


COMPOSE_FILE = Path(os.environ.get(
    "GAME_STACK_COMPOSE_FILE",
    Path(__file__).resolve().parents[2] / "game-stack" / "docker-compose.yml",
))
PROJECT_LABEL = "com.docker.compose.project=game-stack"


def _run_json(command, timeout=5):
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=timeout)
    return json.loads(result.stdout)


def _container_environment(container):
    return {
        key: value
        for item in container.get("Config", {}).get("Env", [])
        if "=" in item
        for key, value in [item.split("=", 1)]
    }


def _memory_in_gb(value):
    match = re.fullmatch(r"\s*(\d+)\s*([GMgm]?)\s*", str(value or ""))
    if not match:
        return 1
    amount, unit = int(match.group(1)), match.group(2).upper()
    return max(1, amount if unit != "M" else round(amount / 1024))


def _compose_port(service):
    for port in service.get("ports") or []:
        if int(port.get("target", 0)) == 25565 and port.get("protocol", "tcp") == "tcp":
            try:
                return int(port["published"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _container_port(container):
    published = container.get("HostConfig", {}).get("PortBindings", {}).get("25565/tcp") or []
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


def _compose_inventory():
    return _run_json([
        "docker", "compose", "--profile", "*", "-f", str(COMPOSE_FILE),
        "config", "--format", "json",
    ])


def _service_and_profile(container_name):
    services = (_compose_inventory().get("services") or {})
    for service_name, service in services.items():
        if (service.get("container_name") or service_name) == container_name:
            profiles = service.get("profiles") or []
            profile = profiles[0] if profiles else service_name
            profile_services = [
                name for name, configured in services.items()
                if profile in (configured.get("profiles") or [])
            ]
            return service_name, profile, profile_services
    raise ValueError("This container is not an allowlisted game-stack service.")


def _run_compose(arguments, timeout=120):
    try:
        return subprocess.run(
            ["docker", "compose", "--profile", arguments[0], "-f", str(COMPOSE_FILE), *arguments[1:]],
            capture_output=True, text=True, check=True, timeout=timeout,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.stderr.strip() or "Docker Compose command failed.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Docker Compose did not finish in time.") from error


def set_server_power(container_name, action):
    """Start or stop a configured game profile and its supporting services."""
    if action not in {"start", "stop"}:
        raise ValueError("Unsupported power action.")
    _, profile, profile_services = _service_and_profile(container_name)
    compose_action = ["up", "-d"] if action == "start" else ["stop"]
    _run_compose([profile, *compose_action, *profile_services])


def sync_docker_game_servers():
    """Use Compose for inventory and Docker for current activity state."""
    try:
        compose = _compose_inventory()
        listed = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"label={PROJECT_LABEL}", "--format", "{{.ID}}"],
            capture_output=True, text=True, check=True, timeout=3,
        )
        container_ids = listed.stdout.split()
        containers = _run_json(["docker", "inspect", *container_ids]) if container_ids else []
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        return str(error)

    containers_by_name = {
        container.get("Name", "").lstrip("/"): container
        for container in containers
    }
    configured_names = set()

    for service_name, service in (compose.get("services") or {}).items():
        image = service.get("image", "")
        if service_name.endswith("-backup") or "mc-backup" in image:
            continue

        name = service.get("container_name") or service_name
        configured_names.add(name)
        container = containers_by_name.get(name)
        environment = service.get("environment") or {}
        if container:
            environment = {**environment, **_container_environment(container)}

        defaults = {
            "game": "Minecraft" if "minecraft" in image else service_name.replace("-", " ").title(),
            "allocated_memory": _memory_in_gb(environment.get("MEMORY")),
            "version": str(environment.get("VERSION", "")),
            "port": _container_port(container) if container else _compose_port(service),
            "is_active": bool(container and container.get("State", {}).get("Status") == "running"),
        }
        server = GameServer.objects.filter(container_name=name).first()
        if server is None:
            GameServer.objects.create(
                container_name=name,
                world_name=name.upper(),
                slug=_unique_slug(name),
                notes="",
                **defaults,
            )
        else:
            for field, value in defaults.items():
                setattr(server, field, value)
            server.save(update_fields=list(defaults))

    GameServer.objects.exclude(container_name__in=configured_names).delete()
    return None

