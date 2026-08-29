from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Sum
from .models import GameServer
from .docker_sync import live_memory_usage, sync_docker_game_servers, set_server_power


@login_required
def dashboard(request):
    docker_error = sync_docker_game_servers()
    servers = GameServer.objects.all().order_by('-is_active', 'world_name')
    server_count = servers.count()
    memory_usage = live_memory_usage([server.container_name for server in servers if server.is_active])
    for server in servers:
        server.memory_usage_mb = memory_usage.get(server.container_name)
    active_count = servers.filter(is_active=True).count()
    context = {
        'servers': servers,
        'server_count': server_count,
        'active_count': active_count,
        'stopped_count': server_count - active_count,
        'total_memory': servers.aggregate(total=Sum('allocated_memory'))['total'] or 0,
        'docker_error': docker_error,
    }
    return render(request, 'dashboard.html', context)


@login_required
def game_server_detail(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Clean Django shortcut to avoid typing out try/except block
    server.memory_usage_mb = live_memory_usage([server.container_name]).get(server.container_name) if server.is_active else None
    return render(request, 'game_server_detail.html', {'server': server})


@staff_member_required(login_url="/admin/login/")
@require_POST
def server_power(request, slug):
    server = get_object_or_404(GameServer, slug=slug)
    action = request.POST.get("action", "")
    try:
        set_server_power(server.container_name, action)
        sync_docker_game_servers()
        result = "started" if action == "start" else "stopped"
        messages.success(request, f"{server.world_name} was {result} successfully.")
    except (ValueError, RuntimeError, OSError) as error:
        messages.error(request, str(error))
    return redirect("game_server_detail", slug=slug)
