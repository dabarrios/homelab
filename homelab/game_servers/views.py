from django.shortcuts import render
from django.http import HttpResponse
from .data import get_server_list, get_server_details

def servers_overview(request):
    servers = get_server_list()

    return render(request, 'servers_overview.html', {'servers': servers})

def server_details(request, slug):
    server = get_server_details(slug)

    if not server:
        return HttpResponse('Server not found', status=404)

    return render(request, 'server_details.html', {'server': server})