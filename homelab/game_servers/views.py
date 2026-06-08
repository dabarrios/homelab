from django.shortcuts import render
from django.http import HttpResponse
from .models import GameServer

def game_server_list(request):
    servers = GameServer.objects.all().order_by('name')
    total_servers = servers.count()
    active_servers = servers.filter(is_active=True).count()
    stopped_servers = total_servers - active_servers
    total_memory = sum(server.allocated_memory for server in servers)
    selected_server = servers.first()

    context = {
        'servers': servers,
        'total_servers': total_servers,
        'active_servers': active_servers,
        'stopped_servers': stopped_servers,
        'total_memory': total_memory,
        'selected_server': selected_server,
    }

    return render(request, 'game_server_list.html', context)

def game_server_detail(request, slug):
    try:
        server = GameServer.objects.get(slug=slug)
    except GameServer.DoesNotExist:
        return HttpResponse('Server not found', status=404)
    return render(request, 'game_server_detail.html', {'server': server})
