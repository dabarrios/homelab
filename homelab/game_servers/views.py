from django.shortcuts import render
from django.http import HttpResponse
from .models import GameServer

def game_server_list(request):
    servers = GameServer.objects.all()
    return render(request, 'game_server_list.html', {'servers': servers})

def game_server_detail(request, slug):
    try:
        server = GameServer.objects.get(slug=slug)
    except GameServer.DoesNotExist:
        return HttpResponse('Server not found', status=404)
    return render(request, 'game_server_detail.html', {'server': server})