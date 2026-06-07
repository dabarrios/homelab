from django.shortcuts import render
from django.http import HttpResponse

def game_status(request):
    return HttpResponse("Hello, world!")