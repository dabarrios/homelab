from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from .models import GameServer
from .forms import GameServerNotesForm

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