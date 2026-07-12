from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Sum
from django.views.decorators.http import require_POST, require_GET
from .models import GameServer
from .docker_sync import sync_docker_game_servers
from .forms import GameServerNotesForm, GameServerAllocatedMemoryForm, GameServerContainerNameForm, GameServerGameNameForm, GameServerIsActiveForm, GameServerPortForm, GameServerSlugForm, GameServerVersionForm, GameServerWorldNameForm

def game_server_list(request):
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

@require_POST
def update_server_details(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Set server equal to some existing GameServer object
    form = None
    
    if "game" in request.POST:
        form = GameServerGameNameForm(request.POST, instance=server)
        updated_field = "game"
    elif "world_name" in request.POST:
        form = GameServerWorldNameForm(request.POST, instance=server)
        updated_field = "world_name"
    elif "slug" in request.POST:
        form = GameServerSlugForm(request.POST, instance=server)
        updated_field = "slug"
    elif "container_name" in request.POST:
        form = GameServerContainerNameForm(request.POST, instance=server)
        updated_field = "container_name"
    elif "allocated_memory" in request.POST:
        form = GameServerAllocatedMemoryForm(request.POST, instance=server)
        updated_field = "allocated_memory"
    elif "version" in request.POST:
        form = GameServerVersionForm(request.POST, instance=server)
        updated_field = "version"
    elif "port" in request.POST:
        form = GameServerPortForm(request.POST, instance=server)
        updated_field = "port"
    elif "is_active" in request.POST:
        form = GameServerIsActiveForm(request.POST, instance=server)
        updated_field = "is_active"
    elif "notes" in request.POST:
        form = GameServerNotesForm(request.POST, instance=server)  # Create form using submitted data and updates that specific server
        updated_field = "notes"

    if form is None:
        return JsonResponse({
            "status": "error",
            "message": "No supported field was submitted.",
        }, status=400)
    
    if form.is_valid():         # Checking if submitted data is valid
        server = form.save()    # Update database
        # Returns success and the new notes field value
        return JsonResponse({
            "status": "success",
            "field": updated_field,
            "value": getattr(server, updated_field),
        })
    
    return JsonResponse({
        "status": "error",
        "errors": form.errors,
    }, status=400)