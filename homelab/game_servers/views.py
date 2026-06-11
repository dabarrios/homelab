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

def game_server_edit_detail(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Clean Django shortcut to avoid typing out try/except block

    if request.method == "POST":    # Checking if form is submitted
        form = GameServerNotesForm(request.POST, instance=server)   # Create form using submitted data and updates that specific server

        if form.is_valid(): # Checking if submitted data is valid
            form.save()     # Update database
            # Django will check the server GameServer object for a get_absolute_url() and redirects
            return redirect(server)
    else:
        form = GameServerNotesForm(instance=server)

    return render(request, "game_server_edit_detail.html", {"form": form, "server": server})

@require_POST
def update_server_notes(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Set server equal to some existing GameServer object
    server.notes = request.POST.get("notes", "")        # Grab the new updated notes when self.client.post is used
    server.save() # Save changes
    
    # Returns success and the new notes field value
    return JsonResponse({
        "status": "success",
        "notes": server.notes,
    })

@require_POST
def update_server_details(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Set server equal to some existing GameServer object
    form = None
    
    if "game" in request.POST:
        form = GameServerGameNameForm(request.POST, instance=server)
    elif "world_name" in request.POST:
        form = GameServerWorldNameForm(request.POST, instance=server)
    elif "slug" in request.POST:
        form = GameServerSlugForm(request.POST, instance=server)
    elif "container_name" in request.POST:
        form = GameServerContainerNameForm(request.POST, instance=server)
    elif "allocated_memory" in request.POST:
        form = GameServerAllocatedMemoryForm(request.POST, instance=server)
    elif "version" in request.POST:
        form = GameServerVersionForm(request.POST, instance=server)
    elif "port" in request.POST:
        form = GameServerPortForm(request.POST, instance=server)
    elif "is_active" in request.POST:
        form = GameServerIsActiveForm(request.POST, instance=server)
    elif "notes" in request.POST:
        form = GameServerNotesForm(request.POST, instance=server)  # Create form using submitted data and updates that specific server

    if form.is_valid():         # Checking if submitted data is valid
        server = form.save()    # Update database
        # Returns success and the new notes field value
        return JsonResponse({
            "status": "success",
            "game": server.game,
            "world_name": server.world_name,
            "slug": server.slug,
            "container_name": server.container_name,
            "allocated_memory": server.allocated_memory,
            "version": server.version,
            "port": server.port,
            "is_active": server.is_active,
            "notes": server.notes,
        })
        
    return JsonResponse({
        "status": "error",
        "errors": form.errors,
    }, status=400)
