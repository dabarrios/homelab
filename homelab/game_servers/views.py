from django.shortcuts import render
from django.http import HttpResponse
from .data import get_server_list, get_server_details

def game_server_list(request):
    servers = get_server_list()

    return render(request, 'game_server_list.html', {'servers': servers})

def game_server_detail(request, slug):
    server = get_server_details(slug)

    if not server:
        return HttpResponse('Server not found', status=404)

    return render(request, 'game_server_detail.html', {'server': server})