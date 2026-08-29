from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import bases as bases_service
from .services import breeding as breeding_service
from .services import data as data_service
from .services import ivs as ivs_service
from .services import ranch as ranch_service
from .services import saves as saves_service
from .services import work as work_service


MODULES = [
    {"key": "breeding", "title": "Breeding", "route": "pals:breeding", "summary": "Plan clean passive routes from owned Pals."},
    {"key": "ivs", "title": "IVs", "route": "pals:ivs", "summary": "Compare target lines for stat inheritance."},
    {"key": "work", "title": "Work", "route": "pals:work", "summary": "Rank candidates by work suitability."},
    {"key": "ranch", "title": "Ranch", "route": "pals:ranch", "summary": "Find ranch drops and passive priorities."},
    {"key": "bases", "title": "Bases", "route": "pals:bases", "summary": "Draft base worker teams by role."},
]


def module_context(active: str, status: dict[str, str]) -> dict:
    return {
        "active": active,
        "modules": MODULES,
        "status": status,
    }


@login_required
def home(request):
    return render(
        request,
        "pals/home.html",
        {
            "modules": MODULES,
            "data_status": data_service.module_status(),
            "sync_status": saves_service.module_status(),
        },
    )


@login_required
def breeding(request):
    return render(request, "pals/breeding.html", module_context("breeding", breeding_service.module_status()))


@login_required
def ivs(request):
    return render(request, "pals/ivs.html", module_context("ivs", ivs_service.module_status()))


@login_required
def work(request):
    return render(request, "pals/work.html", module_context("work", work_service.module_status()))


@login_required
def ranch(request):
    return render(request, "pals/ranch.html", module_context("ranch", ranch_service.module_status()))


@login_required
def bases(request):
    return render(request, "pals/bases.html", module_context("bases", bases_service.module_status()))
