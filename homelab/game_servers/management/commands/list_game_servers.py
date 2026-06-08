from django.core.management.base import BaseCommand
from game_servers.models import GameServer
import subprocess


def get_docker_status(container_name):
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        return "docker unavailable"
    except subprocess.CalledProcessError:
        return "container not found"

    return result.stdout.strip() or "unknown"


class Command(BaseCommand):
    help = 'List all game servers in the database'

    def handle(self, *args, **options):
        servers = GameServer.objects.all()
        if not servers:
            self.stdout.write(self.style.WARNING('No game servers found.'))
            return

        for server in servers:
            if server.is_active:
                active_status = self.style.SUCCESS("Yes")
            else:
                active_status = self.style.ERROR("No")

            docker_status = get_docker_status(server.container_name)

            self.stdout.write(
                f'Game: {server.game}, Name: {server.name}, Version: {server.version}, '
                f'Container: {server.container_name}, Docker: {docker_status}, '
                f'Port: {server.port}, Active: {active_status}'
            )
