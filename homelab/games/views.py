from django.shortcuts import render
from django.http import HttpResponse

def game_status(request):
    servers = [
        {
            'name': 'Vanilla 2025',
            'slug': 'mc1',
            'version': '1.21.11',
            'memory': '6GB',
            'port': 25565,
            'status': 'stopped',
        },
        {
            'name': 'Solo World 2025',
            'slug': 'mc2',
            'version': '1.21.11',
            'memory': '4GB',
            'port': 25566,
            'status': 'stopped',
        },
        {
            'name': 'Cobbleverse 2026',
            'slug': 'mc3',
            'version': '1.21.11',
            'memory': '8GB',
            'port': 25567,
            'status': 'stopped',
        },
    ]
    return render(request, 'games_status.html', {'servers': servers})