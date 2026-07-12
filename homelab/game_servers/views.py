from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from .models import GameServer
from .docker_sync import sync_docker_game_servers

def dashboard(request):
    docker_error = sync_docker_game_servers()
    servers = GameServer.objects.all().order_by('-is_active', 'world_name')
    server_count = servers.count()
    active_count = servers.filter(is_active=True).count()
    context = {
        'servers': servers,
        'server_count': server_count,
        'active_count': active_count,
        'stopped_count': server_count - active_count,
        'total_memory': servers.aggregate(total=Sum('allocated_memory'))['total'] or 0,
        'docker_error': docker_error,
    }
    return render(request, 'game_server_list.html', context)

def game_server_detail(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Clean Django shortcut to avoid typing out try/except block
    return render(request, 'game_server_detail.html', {'server': server})
