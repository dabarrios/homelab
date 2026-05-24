#!/usr/bin/env python3

from pathlib import Path
import subprocess

stacks = [
    "automation-stack",
    "cloud-stack",
    "database-stack",
    "dns-stack",
    "frontend-stack",
    "game-stack",
    "immich-stack",
    "management-stack",
    "monitoring-stack",
    "paperless-stack",
    "utilities-stack",
    "vpn-stack",
]

repo = Path(__file__).resolve().parent.parent

for stack in stacks:
    path = repo / stack

    if not path.exists():
        print(f"skipping {stack}, folder not found")
        continue

    if not (path / "docker-compose.yml").exists():
        print(f"skipping {stack}, no compose file")
        continue

    print(f"\n--- {stack} ---")
    subprocess.run(["docker", "compose", "down"], cwd=path, check=True)
    subprocess.run(["docker", "compose", "pull"], cwd=path, check=True)
    subprocess.run(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=path, check=True)