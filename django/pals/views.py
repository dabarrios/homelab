from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services import bases as bases_service
from .services import breeding as breeding_service
from .services import data as data_service
from .services import ivs as ivs_service
from .services import optimizer
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


def app_context(active: str, title: str, summary: str, module_key: str, action_label: str) -> dict[str, str | list[dict[str, str]]]:
    return {
        "active": active,
        "title": title,
        "summary": summary,
        "module_key": module_key,
        "action_label": action_label,
        "modules": MODULES,
    }


def json_payload(request) -> dict:
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def json_error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "error": message}, status=status)


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
    return render(request, "pals/breeding.html", app_context("breeding", "Breeding", breeding_service.module_status()["message"], "breeding", "Optimize"))


@login_required
def ivs(request):
    return render(request, "pals/ivs.html", app_context("ivs", "IVs", ivs_service.module_status()["message"], "ivs", "Calculate IVs"))


@login_required
def work(request):
    return render(request, "pals/work.html", app_context("work", "Work", work_service.module_status()["message"], "work", "Find Workers"))


@login_required
def ranch(request):
    return render(request, "pals/ranch.html", app_context("ranch", "Ranch", ranch_service.module_status()["message"], "ranch", "Find Drops"))


@login_required
def bases(request):
    return render(request, "pals/bases.html", app_context("bases", "Bases", bases_service.module_status()["message"], "bases", "Plan Base"))


@login_required
@require_GET
def options(request):
    return JsonResponse({
        "species": optimizer.STORE.species_names,
        "passives": optimizer.STORE.passives,
        "passivesByOwner": optimizer.STORE.passives_by_owner,
        "passiveMeta": optimizer.STORE.passive_meta,
        "speciesMeta": optimizer.species_meta(),
        "owners": optimizer.STORE.owners,
        "workTypes": [
            {"key": key, "label": label}
            for key, label in sorted(optimizer.WORK_LABELS.items(), key=lambda item: item[1])
        ],
        "baseSites": optimizer.base_work_sites_payload(),
        "implantInventory": optimizer.load_implant_inventory(),
        "rosterCount": len(optimizer.STORE.roster),
        "dataVersion": optimizer.STORE.breeding_data.get("dataVersion"),
        "generatedAt": optimizer.STORE.breeding_data.get("generatedAt"),
    })


@login_required
@require_GET
def work_suitability(request):
    return JsonResponse(optimizer.work_suitability_payload(
        owner=request.GET.get("owner", ""),
        selected_work=request.GET.get("work", ""),
    ))


@login_required
@require_GET
def ranch_drops(request):
    return JsonResponse(optimizer.ranch_drops_payload(owner=request.GET.get("owner", "")))


@login_required
@require_GET
def base_work_sites(request):
    return JsonResponse(optimizer.base_work_sites_payload())


@login_required
@require_GET
def owned_target_pals(request):
    return JsonResponse(optimizer.owned_target_pals_payload(
        request.GET.get("owner", "David"),
        request.GET.get("target", ""),
    ))


@login_required
@require_GET
def reload_data(request):
    optimizer.STORE.reload()
    optimizer.BASE_WORK_CACHE["payload"] = None
    optimizer.BASE_WORK_CACHE["mtime"] = None
    return JsonResponse({"ok": True, "rosterCount": len(optimizer.STORE.roster)})


@login_required
@require_GET
def live_save_status(request):
    return JsonResponse(optimizer.live_save_status())


@login_required
@require_GET
def pal_asset(request, name: str):
    file_path = (optimizer.PAL_IMAGES / Path(name).name).resolve()
    try:
        images_root = optimizer.PAL_IMAGES.resolve()
    except OSError as exc:
        raise Http404 from exc
    if not str(file_path).startswith(str(images_root)) or not file_path.exists():
        raise Http404
    return FileResponse(file_path.open("rb"), content_type="image/png")


@login_required
@csrf_exempt
@require_POST
def upload_save(request):
    if not request.body:
        return json_error("No file data received")
    optimizer.UPLOADS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    content_type = request.META.get("CONTENT_TYPE", "")
    try:
        files = optimizer.multipart_files(request.META.get("CONTENT_TYPE", ""), request.body) if content_type.startswith("multipart/form-data") else []
        if not files:
            files = [(request.META.get("HTTP_X_FILENAME", "Level.sav"), request.body)]
        upload_dir = optimizer.save_uploaded_files(files, stamp)
        uploaded_files = [p for p in upload_dir.rglob("*") if p.is_file()]
        if len(uploaded_files) == 1 and uploaded_files[0].suffix.lower() == ".zip":
            upload_dir = optimizer.expand_zip_upload(uploaded_files[0], stamp)
        return JsonResponse(optimizer.run_decode_from_save_dir(upload_dir, str(upload_dir.relative_to(optimizer.ROOT))))
    except zipfile.BadZipFile:
        return json_error("Uploaded .zip is not a valid zip file")
    except Exception as exc:
        return json_error(str(exc), status=500)


@login_required
@csrf_exempt
@require_POST
def upload_level(request):
    if not request.body:
        return json_error("No file data received")
    optimizer.UPLOADS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    upload_path = optimizer.UPLOADS / f"Level-{stamp}.sav"
    upload_path.write_bytes(request.body)
    return JsonResponse(optimizer.run_decode_from_level(upload_path))


@login_required
@csrf_exempt
@require_POST
def live_save_refresh(request):
    result = optimizer.refresh_live_save(force=bool(json_payload(request).get("force")))
    return JsonResponse(result, status=409 if result.get("refreshing") and not result.get("ok") else 200)


@login_required
@csrf_exempt
@require_POST
def optimize(request):
    return JsonResponse(optimizer.build_plan(json_payload(request)))


@login_required
@csrf_exempt
@require_POST
def profile_passives(request):
    result = optimizer.profile_passives_payload(json_payload(request))
    return JsonResponse(result, status=400 if not result.get("ok") else 200)


@login_required
@csrf_exempt
@require_POST
def improve_ivs(request):
    return JsonResponse(optimizer.build_iv_plan(json_payload(request)))


@login_required
@csrf_exempt
@require_POST
def base_labels(request):
    payload = json_payload(request)
    labels = optimizer.load_base_labels()
    base_id = str(payload.get("baseId") or "")
    label = str(payload.get("label") or "").strip()
    if not base_id:
        return json_error("Missing baseId")
    if label:
        labels[base_id] = label[:80]
    else:
        labels.pop(base_id, None)
    optimizer.save_base_labels(labels)
    optimizer.BASE_WORK_CACHE["payload"] = None
    return JsonResponse({"ok": True, "labels": labels})


@login_required
@csrf_exempt
@require_POST
def implant_inventory(request):
    payload = json_payload(request)
    inventory = optimizer.load_implant_inventory()
    passive = str(payload.get("passive") or "").strip()
    if not passive:
        return json_error("Missing passive")
    if payload.get("delete"):
        inventory.pop(passive, None)
    else:
        infinite = bool(payload.get("infinite"))
        count = max(0, optimizer.as_int(payload.get("count")))
        inventory[passive] = {"infinite": infinite, "count": None if infinite else count}
    optimizer.save_implant_inventory(inventory)
    return JsonResponse({"ok": True, "inventory": inventory})


@login_required
@csrf_exempt
@require_POST
def base_planner(request):
    return JsonResponse(optimizer.build_base_planner(json_payload(request)))
