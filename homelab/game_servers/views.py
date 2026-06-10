from django.shortcuts import render
from django.http import HttpResponse
from .models import GameServer
from .forms import GameServerNotesForm

def game_server_list(request):
    servers = GameServer.objects.all()
    return render(request, 'game_server_list.html', {'servers': servers})

def game_server_detail(request, slug):
    try:
        server = GameServer.objects.get(slug=slug)
    except GameServer.DoesNotExist:
        return HttpResponse('Server not found', status=404)
    return render(request, 'game_server_detail.html', {'server': server})

def game_server_edit_notes(request, slug):
    server = get_object_or_404(GameServer, slug=slug)   # Clean Django shortcut to avoid typing out try/except block

    if request.method == "POST":
        form = GameServerNotesForm(request.POST, instance=server)

        if form.is_valid(): # Checking submitted data
            form.save()     # Update database
            return redirect("game_server_detail", slug=server.slug) # Sends user back to the detail page
    else:
        form = GameServerNotesForm(instance=server)

    return render(request, "game_server_edit_notes.html", {"form": form, "server": server})