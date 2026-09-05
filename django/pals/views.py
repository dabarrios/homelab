from __future__ import annotations

import json
import mimetypes
import zipfile
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

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
def ranch(request, item_slug: str = ""):
    context = app_context("ranch", "Ranch", ranch_service.module_status()["message"], "ranch", "Find Ranchers")
    context["ranch_item_slug"] = item_slug
    return render(request, "pals/ranch.html", context)


@login_required
def bases(request):
    return render(request, "pals/bases.html", app_context("bases", "Bases", bases_service.module_status()["message"], "bases", "Build Best Team"))


@login_required
@require_GET
def options(request):
    return JsonResponse({
        "species": data_service.STORE.species_names,
        "passives": data_service.STORE.passives,
        "passivesByOwner": data_service.STORE.passives_by_owner,
        "passiveMeta": data_service.STORE.passive_meta,
        "speciesMeta": work_service.species_meta(),
        "owners": data_service.STORE.owners,
        "workTypes": [
            {"key": key, "label": label}
            for key, label in sorted(data_service.WORK_LABELS.items(), key=lambda item: item[1])
        ],
        "baseSites": bases_service.base_work_sites_payload(),
        "implantInventory": ivs_service.load_implant_inventory(),
        "passiveColorOverrides": data_service.load_passive_color_overrides(),
        "rosterCount": len(data_service.STORE.roster),
        "dataVersion": data_service.STORE.breeding_data.get("dataVersion"),
        "generatedAt": data_service.STORE.breeding_data.get("generatedAt"),
    })


@login_required
@require_GET
def work_suitability(request):
    return JsonResponse(work_service.work_suitability_payload(
        owner=request.GET.get("owner", ""),
        selected_work=request.GET.get("work", ""),
        include_self_breeders=request.GET.get("includeSelfBreeders", "1") not in {"0", "false", "False"},
    ))


@login_required
@require_GET
def ranch_drops(request):
    return JsonResponse(ranch_service.ranch_drops_payload(
        owner=request.GET.get("owner", ""),
        include_self_breeders=request.GET.get("includeSelfBreeders", "1") not in {"0", "false", "False"},
    ))


@login_required
@require_GET
def base_work_sites(request):
    return JsonResponse(bases_service.base_work_sites_payload())


@login_required
@require_GET
def owned_target_pals(request):
    return JsonResponse(ivs_service.owned_target_pals_payload(
        request.GET.get("owner", "David"),
        request.GET.get("target", ""),
    ))


@login_required
@require_POST
def reload_data(request):
    data_service.STORE.reload()
    bases_service.clear_base_work_cache()
    return JsonResponse({"ok": True, "rosterCount": len(data_service.STORE.roster)})


@login_required
@require_GET
def live_save_status(request):
    return JsonResponse(saves_service.live_save_status())


@login_required
@require_GET
def pal_asset(request, name: str):
    file_path = work_service.pal_image_path(name)
    if not file_path:
        raise Http404
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return FileResponse(file_path.open("rb"), content_type=content_type)


@login_required
@require_POST
def upload_save(request):
    data_service.UPLOADS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    content_type = request.META.get("CONTENT_TYPE", "")
    try:
        if content_type.startswith("multipart/form-data"):
            uploads = [file for _, items in request.FILES.lists() for file in items]
            paths = json.loads(request.POST.get("relativePaths", "null"))
            if paths is None:
                paths = [file.name for file in uploads]
            if not isinstance(paths, list) or len(paths) != len(uploads) or not all(isinstance(name, str) for name in paths):
                return json_error("Invalid upload paths")
            files = [(name, file.read()) for name, file in zip(paths, uploads)]
        else:
            files = [(request.META.get("HTTP_X_FILENAME", "Level.sav"), request.body)] if request.body else []
        if not files:
            return json_error("No file data received")
        upload_dir = saves_service.save_uploaded_files(files, stamp)
        uploaded_files = [p for p in upload_dir.rglob("*") if p.is_file()]
        if len(uploaded_files) == 1 and uploaded_files[0].suffix.lower() == ".zip":
            upload_dir = saves_service.expand_zip_upload(uploaded_files[0], stamp)
        return JsonResponse(saves_service.run_decode_from_save_dir(upload_dir, str(upload_dir.relative_to(data_service.ROOT))))
    except json.JSONDecodeError:
        return json_error("Invalid upload paths")
    except zipfile.BadZipFile:
        return json_error("Uploaded .zip is not a valid zip file")
    except Exception as exc:
        return json_error(str(exc), status=500)


@login_required
@require_POST
def upload_level(request):
    if not request.body:
        return json_error("No file data received")
    data_service.UPLOADS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    upload_path = data_service.UPLOADS / f"Level-{stamp}.sav"
    upload_path.write_bytes(request.body)
    return JsonResponse(saves_service.run_decode_from_level(upload_path))


@login_required
@require_POST
def live_save_refresh(request):
    try:
        result = saves_service.refresh_live_save(force=bool(json_payload(request).get("force")))
        return JsonResponse(result, status=409 if result.get("refreshing") and not result.get("ok") else 200)
    except Exception as exc:
        return json_error(str(exc), status=500)


@login_required
@require_POST
def optimize(request):
    return JsonResponse(breeding_service.build_plan(json_payload(request)))


@login_required
@require_POST
def profile_passives(request):
    result = breeding_service.profile_passives_payload(json_payload(request))
    return JsonResponse(result, status=400 if not result.get("ok") else 200)


@login_required
@require_POST
def improve_ivs(request):
    return JsonResponse(ivs_service.build_iv_plan(json_payload(request)))


@login_required
@require_POST
def base_labels(request):
    payload = json_payload(request)
    labels = bases_service.load_base_labels()
    base_id = str(payload.get("baseId") or "")
    label = str(payload.get("label") or "").strip()
    if not base_id:
        return json_error("Missing baseId")
    if label:
        labels[base_id] = label[:80]
    else:
        labels.pop(base_id, None)
    bases_service.save_base_labels(labels)
    bases_service.clear_base_work_cache()
    return JsonResponse({"ok": True, "labels": labels})


@login_required
@require_POST
def implant_inventory(request):
    payload = json_payload(request)
    inventory = ivs_service.load_implant_inventory()
    passive = str(payload.get("passive") or "").strip()
    if not passive:
        return json_error("Missing passive")
    if payload.get("delete"):
        inventory.pop(passive, None)
    else:
        infinite = bool(payload.get("infinite"))
        count = max(0, data_service.as_int(payload.get("count")))
        inventory[passive] = {"infinite": infinite, "count": None if infinite else count}
    ivs_service.save_implant_inventory(inventory)
    return JsonResponse({"ok": True, "inventory": inventory})


@login_required
@require_POST
def passive_colors(request):
    payload = json_payload(request)
    overrides = data_service.load_passive_color_overrides()
    passive = str(payload.get("passive") or "").strip()
    if not passive:
        return json_error("Missing passive")
    canonical = next((item for item in data_service.STORE.passives if item.lower() == passive.lower()), passive)
    if payload.get("delete"):
        overrides.pop(canonical, None)
    else:
        tone = str(payload.get("tone") or "").strip()
        if tone not in data_service.PASSIVE_TONES:
            return json_error("Choose a valid passive color")
        overrides[canonical] = tone
    data_service.save_passive_color_overrides(overrides)
    data_service.STORE.passive_meta = data_service.build_passive_meta(data_service.STORE.passives)
    return JsonResponse({"ok": True, "overrides": overrides, "passiveMeta": data_service.STORE.passive_meta})


@login_required
@require_POST
def base_planner(request):
    return JsonResponse(bases_service.build_base_planner(json_payload(request)))
