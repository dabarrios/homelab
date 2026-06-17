from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .models import GameServer
from .forms import GameServerNotesForm, GameServerAllocatedMemoryForm, GameServerContainerNameForm, GameServerGameNameForm, GameServerIsActiveForm, GameServerPortForm, GameServerSlugForm, GameServerVersionForm, GameServerWorldNameForm

def game_server_list(request):
    servers = GameServer.objects.all()
    return render(request, 'game_server_list.html', {'servers': servers})

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

    if form.is_valid():         # Checking if submitted data is valid
        server = form.save()    # Update database
        # Returns success and the new notes field value
        return redirect(server)
    
    return JsonResponse({
        "status": "success",
        "slug": server.slug,
    })