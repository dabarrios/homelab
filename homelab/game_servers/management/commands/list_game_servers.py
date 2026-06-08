from django.core.management.base import BaseCommand
from game_servers.models import GameServer

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
            self.stdout.write(f'Game: {server.game}, Name: {server.name}, Version: {server.version}, Port: {server.port}, Active: {active_status}')