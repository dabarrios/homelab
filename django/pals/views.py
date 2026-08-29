from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Sum

def home(request):
    # Placeholder for the home view
    return render(request, 'base.html', {})

def breeding(request):
    # Placeholder for the breeding view
    return render(request, 'breeding.html', {})

def ivs(request):
    # Placeholder for the IVs view
    return render(request, 'ivs.html', {})

def work(request):
    # Placeholder for the work view
    return render(request, 'work.html', {})

def base_planner(request):
    # Placeholder for the base planner view
    return render(request, 'base_planner.html', {})
