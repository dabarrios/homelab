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
COMPOSE_ENV_FILE = Path(os.environ.get(
    "GAME_STACK_ENV_FILE",
    Path(__file__).resolve().parents[2] / ".env",
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


def _first(environment, *keys):
    return next((str(environment[key]) for key in keys if environment.get(key) not in (None, "")), "")


def _container_version(container_name, environment):
    command = environment.get("DASHBOARD_VERSION_COMMAND", "").replace("$$", "$")
    if not command:
        return _first(environment, "DASHBOARD_VERSION", "VERSION", "GAME_VERSION", "SERVER_VERSION")
    try:
        result = subprocess.run(
            ["docker", "exec", container_name, "sh", "-lc", command],
            capture_output=True, text=True, check=True, timeout=3,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _memory_in_gb(value):
    match = re.fullmatch(r"\s*(\d+)\s*([GMgm]?)\s*", str(value or ""))
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).upper()
    return max(1, amount if unit != "M" else round(amount / 1024)) if amount else None


def _container_memory(container):
    memory_bytes = (container or {}).get("HostConfig", {}).get("Memory", 0)
    try:
        memory_bytes = int(memory_bytes)
    except (TypeError, ValueError):
        return None
    gibibyte = 1024 ** 3
    return (memory_bytes + gibibyte - 1) // gibibyte if memory_bytes > 0 else None

def _memory_usage_mb(value):
    match = re.match(r"^([0-9.]+)([KMGTP]?i?B)", value or "", re.IGNORECASE)
    if not match:
        return None
    amount, unit = float(match.group(1)), match.group(2).upper()
    factors = {"B": 1 / 1024 ** 2, "KB": 1 / 1024, "KIB": 1 / 1024, "MB": 1, "MIB": 1, "GB": 1024, "GIB": 1024, "TB": 1024 ** 2, "TIB": 1024 ** 2}
    return round(amount * factors[unit])


def live_memory_usage(container_names):
    if not container_names:
        return {}
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_names],
            capture_output=True, text=True, check=True, timeout=8,
        )
        stats = (json.loads(line) for line in result.stdout.splitlines() if line)
        return {item["Name"]: _memory_usage_mb(item.get("MemUsage")) for item in stats}
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}


def _game_port(environment):
    try:
        return int(_first(environment, "DASHBOARD_PORT", "PORT", "GAME_PORT", "SERVER_PORT") or 25565)
    except (TypeError, ValueError):
        return 25565


def _compose_port(service, game_port):
    for port in service.get("ports") or []:
        if int(port.get("target", 0)) == game_port:
            try:
                return int(port["published"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _container_port(container, game_port):
    bindings = container.get("HostConfig", {}).get("PortBindings", {})
    published = bindings.get(f"{game_port}/tcp") or bindings.get(f"{game_port}/udp") or []
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
        "docker", "compose", "--env-file", str(COMPOSE_ENV_FILE), "--profile", "*", "-f", str(COMPOSE_FILE),
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
            ["docker", "compose", "--env-file", str(COMPOSE_ENV_FILE), "--profile", arguments[0], "-f", str(COMPOSE_FILE), *arguments[1:]],
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

        game_port = _game_port(environment)
        defaults = {
            "game": _first(environment, "DASHBOARD_GAME", "GAME") or service_name.replace("-", " ").title(),
            "allocated_memory": (
                _memory_in_gb(_first(environment, "DASHBOARD_MEMORY", "MEMORY")) or _container_memory(container)
            ),
            "version": _container_version(name, environment) if container else _first(
                environment, "DASHBOARD_VERSION", "VERSION", "GAME_VERSION", "SERVER_VERSION"
            ),
            "port": _container_port(container, game_port) if container else _compose_port(service, game_port),
            "is_active": bool(container and container.get("State", {}).get("Status") == "running"),
        }
        server = GameServer.objects.filter(container_name=name).first()
        if server is None:
            GameServer.objects.create(
                container_name=name,
                world_name=_first(environment, "DASHBOARD_NAME", "SERVER_NAME", "WORLD_NAME") or name.upper(),
                slug=_unique_slug(name),
                notes=_first(environment, "DASHBOARD_DESCRIPTION", "SERVER_DESCRIPTION"),
                **defaults,
            )
        else:
            configured_name = _first(environment, "DASHBOARD_NAME", "SERVER_NAME", "WORLD_NAME")
            if configured_name and server.world_name == name.upper():
                defaults["world_name"] = configured_name
            for field, value in defaults.items():
                setattr(server, field, value)
            server.save(update_fields=list(defaults))

    GameServer.objects.exclude(container_name__in=configured_names).delete()
    return None

