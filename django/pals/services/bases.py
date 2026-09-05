"""Base parsing, label persistence, cache ownership, and worker planning."""

from __future__ import annotations

import json
import math
import re

from .data import (
    AUTO_TARGET_CAPS,
    BASE_LABELS_FILE,
    SIZE_ORDER,
    STORE,
    WORK,
    WORK_LABELS,
    WORK_SITE_PATTERNS,
    as_int,
)
from .saves import register_refresh_hook
from .work import (
    best_owned_work_levels,
    owned_species_counts,
    work_card_for_owned_row as _owned_work_card,
    work_card_for_pal,
)


def load_base_labels() -> dict:
    if not BASE_LABELS_FILE.exists():
        return {}
    try:
        data = json.loads(BASE_LABELS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_base_labels(labels: dict) -> None:
    BASE_LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASE_LABELS_FILE.write_text(json.dumps(labels, indent=2, sort_keys=True), encoding="utf-8")


BASE_WORK_CACHE = {"mtime": None, "payload": None}


def clear_base_work_cache() -> None:
    BASE_WORK_CACHE["payload"] = None
    BASE_WORK_CACHE["mtime"] = None


def guid_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "value" in value:
            return guid_text(value.get("value"))
        parts = [value.get(k) for k in ("a", "b", "c", "d") if value.get(k) is not None]
        if parts:
            return "-".join(str(p) for p in parts)
    return str(value or "")


def save_to_map_coords(loc: dict) -> dict[str, float]:
    data_x = float(loc.get("x", 0) or 0)
    data_y = float(loc.get("y", 0) or 0)
    return {
        "x": round((data_y - 158000) / 459, 1),
        "y": round((data_x + 123888) / 459, 1),
        "z": round(float(loc.get("z", 0) or 0) / 100, 1),
    }


def base_coord_text(loc: dict) -> str:
    coords = save_to_map_coords(loc)
    return f"{coords['x']:.0f}, {coords['y']:.0f}"


def infer_work_site_skills(name: str) -> list[str]:
    raw = name or ""
    for pattern, skills in WORK_SITE_PATTERNS:
        if pattern.lower() in raw.lower():
            return list(skills)
    return []


def readable_site_name(value: str) -> str:
    name = re.sub(r"_\d+$", "", value or "Unknown")
    replacements = {
        "FarmBlockV2_wheet": "Wheat Plantation",
        "FarmBlockV2_Berries": "Berry Plantation",
        "FarmBlockV2_Carrot": "Carrot Plantation",
        "FarmBlockV2_Lettuce": "Lettuce Plantation",
        "FarmBlockV2_tomato": "Tomato Plantation",
        "FarmBlockV2_Onion": "Onion Plantation",
        "FarmBlockV2_Potato": "Potato Plantation",
        "BreedFarm": "Breeding Farm",
        "HatchingPalEgg": "Egg Incubator",
        "MonsterFarm": "Ranch",
        "StationDeforest2": "Logging Site",
        "StationDeforest3": "Logging Site",
        "StonePit": "Stone Pit",
        "CoalPit": "Coal Mine",
        "CopperPit_2": "Ore Mining Site II",
        "CopperPit": "Ore Mining Site",
        "QuartzPit": "Pure Quartz Mine",
        "CrystalPit": "Sulfur Mine",
        "OilPump": "Crude Oil Extractor",
        "ElectricGenerator": "Power Generator",
        "HugeKitchen": "Electric Kitchen",
        "CookingStove": "Cooking Pot",
        "CampFire": "Campfire",
        "Refrigerator": "Refrigerator",
        "Cooler": "Cooler",
        "BlastFurnace": "Furnace",
        "FlourMill": "Mill",
        "Clinic": "Medicine Facility",
        "MedicineFacility_01": "Medicine Workbench",
        "Workbench": "Workbench",
        "WorkBench_SkillUnlock": "Pal Gear Workbench",
        "SphereFactory_Black_03": "Sphere Assembly Line",
        "SphereFactory_Black_01": "Sphere Workbench",
        "WeaponFactory_Dirty_03": "Weapon Assembly Line",
        "WeaponFactory_Dirty_01": "Weapon Workbench",
        "Factory_Hard_03": "Production Assembly Line",
        "Factory_Hard_01": "Production Workbench",
        "CompositeDesk": "Monitoring Stand",
    }
    return replacements.get(name, replacements.get(re.sub(r"_\d+$", "", name), re.sub(r"(?<!^)(?=[A-Z])", " ", name).replace("_", " ").strip()))


def load_level_world_data() -> dict:
    level_json = WORK / "Level.full.json"
    if not level_json.exists():
        return {}
    return json.loads(level_json.read_text(encoding="utf-8")).get("properties", {}).get("worldSaveData", {}).get("value", {})


def base_work_sites_payload() -> dict:
    level_json = WORK / "Level.full.json"
    if not level_json.exists():
        return {"ok": False, "error": "No decoded Level.full.json is available. Sync Save first.", "bases": []}
    mtime = level_json.stat().st_mtime_ns
    labels = load_base_labels()
    cached = BASE_WORK_CACHE.get("payload")
    if cached and BASE_WORK_CACHE.get("mtime") == mtime:
        payload = json.loads(json.dumps(cached))
        for base in payload.get("bases", []):
            label = labels.get(base.get("id"), "")
            base["customName"] = label
            base["displayName"] = label or base.get("defaultName")
        payload["labels"] = labels
        return payload

    ws = load_level_world_data()
    if not ws:
        return {"ok": False, "error": "Decoded Level.full.json did not contain worldSaveData.", "bases": []}

    model_to_obj = {}
    for item in ws.get("MapObjectSaveData", {}).get("value", {}).get("values", []):
        raw = item.get("Model", {}).get("value", {}).get("RawData", {}).get("value", {})
        mid = guid_text(raw.get("instance_id"))
        if mid:
            model_to_obj[mid] = item.get("MapObjectId", {}).get("value", "")

    work_by_id = {}
    for item in ws.get("WorkSaveData", {}).get("value", {}).get("values", []):
        raw = item.get("RawData", {}).get("value", {})
        wid = guid_text(raw.get("id"))
        if wid:
            work_by_id[wid] = raw

    bases = []
    for idx, entry in enumerate(ws.get("BaseCampSaveData", {}).get("value", []), 1):
        base = entry.get("value", {})
        raw = base.get("WorkerDirector", {}).get("value", {}).get("RawData", {}).get("value", {})
        base_id = guid_text(raw.get("id")) or f"base-{idx}"
        loc = raw.get("spawn_transform", {}).get("translation", {}) or {}
        work_ids = base.get("WorkCollection", {}).get("value", {}).get("RawData", {}).get("value", {}).get("work_ids", [])
        sites = []
        demand = {key: 0 for key in WORK_LABELS}
        unresolved = 0
        seen = set()
        for wid_value in work_ids:
            wid = guid_text(wid_value)
            wr = work_by_id.get(wid)
            if not wr:
                unresolved += 1
                continue
            define = wr.get("assign_define_data_id") or ""
            obj = model_to_obj.get(guid_text(wr.get("owner_map_object_model_id")), "")
            site_key = (define, obj, guid_text(wr.get("owner_map_object_model_id")))
            if site_key in seen:
                continue
            seen.add(site_key)
            site_name = obj or define or "Unknown"
            skills = infer_work_site_skills(site_name) or infer_work_site_skills(define)
            for skill in skills:
                if skill in demand:
                    demand[skill] += 1
            sites.append({
                "id": wid,
                "defineId": define,
                "objectId": obj,
                "name": readable_site_name(site_name or define),
                "skills": skills,
                "state": wr.get("current_state"),
                "requiredWork": wr.get("required_work_amount"),
                "currentWork": wr.get("current_work_amount"),
            })
        default_name = f"Base {idx} ({base_coord_text(loc)})"
        custom = labels.get(base_id, "")
        bases.append({
            "id": base_id,
            "index": idx,
            "defaultName": default_name,
            "customName": custom,
            "displayName": custom or default_name,
            "coords": save_to_map_coords(loc),
            "rawCoords": {"x": round(float(loc.get("x", 0) or 0), 1), "y": round(float(loc.get("y", 0) or 0), 1), "z": round(float(loc.get("z", 0) or 0), 1)},
            "siteCount": len(sites),
            "unresolvedWorkIds": unresolved,
            "sites": sorted(sites, key=lambda s: (s.get("name", ""), s.get("defineId", ""))),
            "demand": {key: value for key, value in demand.items() if value > 0},
        })
    payload = {"ok": True, "bases": bases, "labels": labels, "workTypes": [{"key": key, "label": label} for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1])]}
    BASE_WORK_CACHE["mtime"] = mtime
    BASE_WORK_CACHE["payload"] = json.loads(json.dumps(payload))
    return payload


def display_owned_location(location: str) -> str:
    match = re.search(
        r"^Base\s+(\d+)\s+@\s+\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)",
        location or "",
        re.I,
    )
    if not match:
        return location or ""
    base_index = as_int(match.group(1))
    x = float(match.group(2))
    y = float(match.group(3))
    payload = base_work_sites_payload()
    bases = payload.get("bases", []) if payload.get("ok") else []
    base = next((item for item in bases if as_int(item.get("index")) == base_index), None)
    if not base and bases:
        base = min(
            bases,
            key=lambda item: (
                (float((item.get("coords") or {}).get("x", 0)) - x) ** 2
                + (float((item.get("coords") or {}).get("y", 0)) - y) ** 2
            ),
        )
    if base:
        return base.get("displayName") or base.get("defaultName") or f"Base {base_index}"
    return f"Base {base_index} @ ({x:.0f}, {y:.0f})"


def planner_auto_target(skill: str, demand_count: int, demand: dict[str, int]) -> int:
    if demand_count <= 0:
        return 0
    if skill in {"cooling", "medicine"}:
        return 1
    if skill == "transporting":
        productive = sum(demand.get(k, 0) for k in ("mining", "farming", "planting", "gathering", "lumbering"))
        return min(AUTO_TARGET_CAPS.get(skill, 5), max(1, math.ceil(productive / 3)))
    return min(AUTO_TARGET_CAPS.get(skill, 3), max(1, math.ceil(demand_count / 2)))


def _planner_targets(base: dict, settings: dict, max_workers: int) -> dict:
    demand = dict(base.get("demand") or {})
    if any(demand.get(k, 0) for k in ("mining", "farming", "planting", "gathering", "lumbering")):
        demand["transporting"] = max(demand.get("transporting", 0), 1)

    targets = {}
    for key in WORK_LABELS:
        cfg = settings.get(key) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            targets[key] = {"enabled": False, "min": 0, "max": 0, "auto": 0, "demand": as_int(demand.get(key)), "autoCap": 0}
            continue
        auto = planner_auto_target(key, as_int(demand.get(key)), demand)
        auto_cap = min(max_workers, max(auto, AUTO_TARGET_CAPS.get(key, 3))) if auto else 0
        min_raw = cfg.get("min", None)
        max_raw = cfg.get("max", None)
        explicit_min = min_raw not in (None, "")
        explicit_max = max_raw not in (None, "")
        default_min = 1 if auto > 0 else 0
        min_value = as_int(min_raw, default_min)
        max_value = as_int(max_raw, max_workers) if explicit_max else max_workers
        max_value = min(max_workers, max(min_value, max_value))
        targets[key] = {
            "enabled": True,
            "min": min_value,
            "max": max_value,
            "auto": auto,
            "demand": as_int(demand.get(key)),
            "autoCap": auto_cap,
            "explicitMin": explicit_min,
            "explicitMax": explicit_max,
        }
    return targets


def _planner_candidates(owner: str, targets: dict, owned_only: bool) -> tuple[list[dict], set[str]]:
    owner_counts = owned_species_counts(owner)
    owner_work_levels = best_owned_work_levels(owner)
    candidates = []
    enabled_skills = {key for key, cfg in targets.items() if cfg["enabled"] and (cfg["max"] > 0 or cfg["min"] > 0)}
    if owned_only:
        for row in STORE.roster:
            if owner and row.get("owner") != owner:
                continue
            card = work_card_for_owned_row(row)
            if not card:
                continue
            levels = {entry["key"]: as_int(entry.get("level")) for entry in card["work"]}
            if not any(levels.get(skill, 0) > 0 for skill in enabled_skills):
                continue
            card["plannerLevels"] = levels
            candidates.append(card)
    else:
        for pal in STORE.breeding_data.get("pals", []):
            card = work_card_for_pal(pal, owner_counts)
            best_levels = owner_work_levels.get(card.get("name", ""), {})
            for entry in card["work"]:
                owned_level = as_int(best_levels.get(entry["key"]))
                if owned_level > 0:
                    entry["plannerCurrentLevel"] = owned_level
                    entry["plannerMaximumLevel"] = max(
                        owned_level,
                        as_int(entry.get("fullyCondensedLevel") or entry.get("level")),
                    )
            levels = {entry["key"]: as_int(entry.get("fullyCondensedLevel") or entry.get("level")) for entry in card["work"]}
            if not any(levels.get(skill, 0) > 0 for skill in enabled_skills):
                continue
            card["plannerLevels"] = levels
            candidates.append(card)
    return candidates, enabled_skills


def _candidate_score(card: dict, skill: str, used_counts: dict[str, int], enabled_skills: set[str]) -> tuple:
    levels = card.get("plannerLevels", {})
    role_level = as_int(levels.get(skill))
    extra_enabled = sum(as_int(levels.get(other)) for other in enabled_skills if other != skill)
    off_role_count = sum(1 for other, level in levels.items() if other != skill and level > 0)
    owned_bonus = 1 if card.get("ownedCount") else 0
    repeat_penalty = used_counts.get(card.get("name", ""), 0)
    score_parts = card.get("plannerPassiveScoreParts") or {}
    direct_speed = as_int(score_parts.get("directSpeed"))
    uptime = as_int(score_parts.get("uptime"))
    operations = as_int(score_parts.get("operations"))
    harmful = as_int(score_parts.get("harmful"))
    total_passive_score = as_int(score_parts.get("total"))
    current_base_bonus = 1 if str(card.get("plannerLocation", "")).startswith("Base") else 0
    size_penalty = SIZE_ORDER.get(card.get("size"), 3)
    return (role_level, direct_speed, uptime, operations, -harmful, total_passive_score, current_base_bonus, owned_bonus, -repeat_penalty, -off_role_count, extra_enabled, -size_penalty, card.get("name", ""))


def _best_for_role(candidates: list[dict], skill: str, used_counts: dict[str, int], enabled_skills: set[str], owned_only: bool) -> dict | None:
    pool = [card for card in candidates if as_int(card.get("plannerLevels", {}).get(skill)) > 0]
    if owned_only:
        used_instances = {key for key, value in used_counts.items() if key.startswith("instance:") and value > 0}
        pool = [card for card in pool if f"instance:{card.get('plannerInstanceId', '')}" not in used_instances]
    if not pool:
        return None
    return max(pool, key=lambda card: _candidate_score(card, skill, used_counts, enabled_skills))


def _allocate_role_slots(targets: dict, candidates: list[dict], max_workers: int) -> list[str]:
    role_slots: list[str] = []
    role_weights = {
        "mining": 14,
        "planting": 12,
        "watering": 12,
        "gathering": 11,
        "handiwork": 10,
        "kindling": 9,
        "electric": 9,
        "lumbering": 8,
        "cooling": 7,
        "farming": 7,
        "transporting": 6,
        "medicine": 4,
    }

    def role_has_candidate(skill: str) -> bool:
        return any(as_int(card.get("plannerLevels", {}).get(skill)) > 0 for card in candidates)

    def role_sort_key(skill: str) -> tuple:
        cfg = targets.get(skill, {})
        return (
            role_weights.get(skill, 1),
            as_int(cfg.get("demand")),
            as_int(cfg.get("auto")),
            WORK_LABELS.get(skill, skill),
        )

    active_roles = [
        key for key, cfg in targets.items()
        if cfg.get("enabled") and cfg.get("max", 0) > 0 and (cfg.get("min", 0) > 0 or cfg.get("auto", 0) > 0 or cfg.get("demand", 0) > 0) and role_has_candidate(key)
    ]

    def add_role(skill: str, amount: int = 1) -> None:
        cfg = targets.get(skill, {})
        for _ in range(max(0, amount)):
            if len(role_slots) >= max_workers:
                return
            if role_slots.count(skill) >= cfg.get("max", max_workers):
                return
            role_slots.append(skill)

    for key in sorted(active_roles, key=role_sort_key, reverse=True):
        cfg = targets[key]
        if cfg.get("explicitMin") and cfg.get("min", 0) > 0:
            add_role(key, cfg["min"])

    for key in sorted(active_roles, key=role_sort_key, reverse=True):
        cfg = targets[key]
        if len(role_slots) >= max_workers:
            break
        if role_slots.count(key) == 0 and (cfg.get("demand", 0) > 0 or cfg.get("auto", 0) > 0):
            add_role(key)

    def next_role(prefer_soft_caps: bool) -> str | None:
        expandable = []
        for key in active_roles:
            cfg = targets[key]
            current = role_slots.count(key)
            if current >= cfg.get("max", max_workers):
                continue
            soft_cap = cfg.get("autoCap", 0) or cfg.get("auto", 0) or 1
            if prefer_soft_caps and current >= soft_cap:
                continue
            target_need = max(0, cfg.get("min", 0) - current)
            soft_need = max(0, soft_cap - current)
            demand_bonus = min(6, as_int(cfg.get("demand")))
            priority = (role_weights.get(key, 1) * 10) + demand_bonus
            if target_need > 0:
                priority += 1000
            elif soft_need > 0:
                priority += 100
            priority -= current * 8
            expandable.append((priority, -current, role_sort_key(key), key))
        if not expandable:
            return None
        expandable.sort(reverse=True)
        return expandable[0][3]

    while len(role_slots) < max_workers:
        key = next_role(prefer_soft_caps=True) or next_role(prefer_soft_caps=False)
        if not key:
            break
        add_role(key)
    return role_slots


def build_base_planner(payload: dict) -> dict:
    base_id = payload.get("baseId", "")
    owner = payload.get("owner", "")
    settings = payload.get("settings") or {}
    planner_mode = payload.get("plannerMode") if payload.get("plannerMode") in {"ideal", "right_now"} else "ideal"
    owned_only = planner_mode == "right_now"
    max_workers = min(15, max(1, as_int(payload.get("maxWorkers"), 15)))
    bases_payload = base_work_sites_payload()
    if not bases_payload.get("ok"):
        return bases_payload
    base = next((item for item in bases_payload.get("bases", []) if item.get("id") == base_id), None) or (bases_payload.get("bases") or [None])[0]
    if not base:
        return {"ok": False, "error": "No bases were found in the decoded save.", "bases": []}

    targets = _planner_targets(base, settings, max_workers)
    candidates, enabled_skills = _planner_candidates(owner, targets, owned_only)
    role_slots = _allocate_role_slots(targets, candidates, max_workers)

    selected = []
    covered = {key: 0 for key in WORK_LABELS}
    used_counts: dict[str, int] = {}
    for idx, skill in enumerate(role_slots[:max_workers], 1):
        card = _best_for_role(candidates, skill, used_counts, enabled_skills, owned_only)
        if not card:
            continue
        item = json.loads(json.dumps(card))
        item["plannerRole"] = skill
        item["plannerSlot"] = idx
        item["selectedWork"] = skill
        item["plannerReasons"] = [f"Primary: {WORK_LABELS[skill]} Lv. {as_int(item.get('plannerLevels', {}).get(skill))}"]
        for other, level in sorted(item.get("plannerLevels", {}).items(), key=lambda entry: (-as_int(entry[1]), WORK_LABELS.get(entry[0], entry[0]))):
            if other != skill and level > 0 and targets.get(other, {}).get("enabled"):
                item["plannerReasons"].append(f"Also {WORK_LABELS[other]} Lv. {level}")
            if len(item["plannerReasons"]) >= 4:
                break
        selected.append(item)
        used_counts[item.get("name", "")] = used_counts.get(item.get("name", ""), 0) + 1
        if item.get("plannerInstanceId"):
            used_counts[f"instance:{item.get('plannerInstanceId')}"] = 1
        if covered.get(skill, 0) < targets.get(skill, {}).get("max", max_workers):
            covered[skill] = covered.get(skill, 0) + 1

    gaps = []
    for key, cfg in targets.items():
        if cfg["enabled"] and cfg["min"] > 0 and covered.get(key, 0) < cfg["min"]:
            gaps.append({"key": key, "label": WORK_LABELS[key], "wanted": cfg["min"], "covered": covered.get(key, 0)})

    return {
        "ok": True,
        "base": base,
        "owner": owner,
        "maxWorkers": max_workers,
        "plannerMode": planner_mode,
        "ownedOnly": owned_only,
        "targets": targets,
        "covered": {key: value for key, value in covered.items() if value > 0},
        "recommendations": selected,
        "roleSlots": role_slots[:max_workers],
        "gaps": gaps,
        "summary": f"{len(selected)} recommended worker slot(s) for {base.get('displayName')}.",
    }


def work_card_for_owned_row(row: dict[str, str]) -> dict | None:
    """Resolve base labels before delegating shared worker scoring."""
    return _owned_work_card(row, display_location=display_owned_location(row.get("location", "") or ""))


register_refresh_hook(clear_base_work_cache)


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "Base parsing and planning are available."}
