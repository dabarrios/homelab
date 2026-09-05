"""Species metadata, work suitability, and shared owned-worker scoring."""

from __future__ import annotations

import json

from pathlib import Path

from .data import (
    LOCAL_PAL_IMAGES,
    PAL_IMAGES,
    POPULAR_WORK_PICKS,
    SIZE_GROUPS,
    SIZE_ORDER,
    STORE,
    VALID_PAL_SIZES,
    WORK_LABELS,
    WORK_OVERRIDES,
    as_int,
    match_key,
    normalize_species,
    split_passives,
)


def pal_image_path(name: str) -> Path | None:
    safe_name = Path(name).name
    for root in (LOCAL_PAL_IMAGES, PAL_IMAGES):
        try:
            file_path = (root / safe_name).resolve()
            root_path = root.resolve()
        except OSError:
            continue
        if str(file_path).startswith(str(root_path)) and file_path.exists():
            return file_path
    return None


def icon_url_for_key(key: str) -> str | None:
    for suffix in (".png", ".webp"):
        name = f"{key}{suffix}"
        if pal_image_path(name):
            return f"/assets/pals/{name}"
    return None


def species_meta() -> dict[str, dict]:
    return {
        pal.get("name", ""): {
            "key": pal.get("key", ""),
            "types": pal.get("types", []),
            "icon": icon_url_for_key(pal.get("key", "")),
        }
        for pal in STORE.breeding_data.get("pals", [])
        if pal.get("name")
    }


def species_types_for_key(key: str) -> list[str]:
    for pal in STORE.breeding_data.get("pals", []):
        if pal.get("key") == key:
            return pal.get("types", [])
    return []


WORK_ORDER_INDEX = {key: idx for idx, key in enumerate(WORK_LABELS)}


def ordered_work_keys(work: dict) -> list[str]:
    return [key for key in WORK_LABELS if as_int(work.get(key)) > 0]


def condensation_rank_targets(work: dict) -> list[str]:
    keys = ordered_work_keys(work)
    if not keys:
        return []
    ranked = sorted(keys, key=lambda key: (-as_int(work.get(key)), WORK_ORDER_INDEX[key]))
    return [ranked[idx % len(ranked)] for idx in range(3)]


def load_work_overrides() -> dict[str, dict]:
    if not WORK_OVERRIDES.exists():
        return {}
    try:
        data = json.loads(WORK_OVERRIDES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {match_key(name): value for name, value in (data.get("overrides") or {}).items()}


WORK_SUITABILITY_OVERRIDES = load_work_overrides()


def work_override_for(name: str) -> dict | None:
    override = WORK_SUITABILITY_OVERRIDES.get(match_key(name))
    if isinstance(override, dict):
        return override
    return None


def palpedia_entry_for(name: str) -> dict | None:
    entry = getattr(STORE, "palpedia_work", {}).get(match_key(name))
    if isinstance(entry, dict):
        return entry
    return None


def work_for_pal(pal: dict) -> dict:
    entry = palpedia_entry_for(pal.get("name", ""))
    if entry:
        return entry.get("baseWork") or {}
    return pal.get("work") or {}


def work_source_for(name: str) -> dict | None:
    entry = palpedia_entry_for(name)
    if entry:
        source = getattr(STORE, "palpedia_work_source", {}) or {}
        fetched = source.get("fetchedAt", "")
        detail = source.get("source", "Palpedia.net Work Suitability")
        if fetched:
            detail = f"{detail}, fetched {fetched}"
        return {"source": detail, "url": source.get("sourceUrl", "")}
    return work_override_for(name)


def projected_fully_condensed_work_levels(work: dict) -> dict[str, int]:
    levels = {key: as_int(work.get(key)) for key in ordered_work_keys(work)}
    for key in condensation_rank_targets(work):
        levels[key] = min(10, levels[key] + 1)
    for key in list(levels):
        levels[key] = min(10, levels[key] + 1)
    return levels


def fully_condensed_work_levels(work: dict, name: str = "") -> dict[str, int]:
    entry = palpedia_entry_for(name)
    if entry:
        verified = entry.get("fullyCondensedWork") or {}
        return {key: as_int(verified.get(key)) for key in WORK_LABELS if as_int(verified.get(key)) > 0}
    override = work_override_for(name)
    if not override:
        return {}
    verified = override.get("fullyCondensedWork") or {}
    return {key: as_int(verified.get(key)) for key in WORK_LABELS if as_int(verified.get(key)) > 0}


def pal_size_for(name: str) -> str:
    entry = palpedia_entry_for(name)
    size = str((entry or {}).get("size") or "").strip().upper()
    if size in VALID_PAL_SIZES:
        return size
    return "Unknown"


def owned_species_counts(owner: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in STORE.roster:
        if owner and row.get("owner") != owner:
            continue
        species = normalize_species(row.get("species", ""))
        if not species:
            continue
        counts[species] = counts.get(species, 0) + 1
    return counts


def work_entries(work: dict, name: str = "") -> list[dict]:
    entries = []
    condensed_levels = fully_condensed_work_levels(work, name)
    projected_levels = projected_fully_condensed_work_levels(work)
    for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1]):
        level = as_int(work.get(key))
        if level <= 0:
            continue
        entries.append({
            "key": key,
            "label": label,
            "level": level,
            "fullyCondensedLevel": condensed_levels.get(key),
            "projectedFullyCondensedLevel": projected_levels.get(key),
        })
    return entries


def card_final_level(card: dict) -> int:
    return as_int(card.get("selectedFullyCondensedLevel") or card.get("selectedLevel"))


def requires_owned_seed_for_breeding(species_key: str) -> bool:
    pairs = STORE.parent_pairs_for_child(species_key)
    return bool(pairs) and all(a == species_key and b == species_key for a, b in pairs)


def work_recommendations(cards: list[dict], selected_work: str, include_self_breeders: bool = True) -> list[dict]:
    if not cards:
        return []
    pick_pool = cards if include_self_breeders else [card for card in cards if not card.get("requiresOwnedSeed")]
    pick_pool = pick_pool or cards

    def best(sort_key):
        return sorted(pick_pool, key=sort_key)[0]

    popular_name = POPULAR_WORK_PICKS.get(selected_work)
    popular = next((card for card in pick_pool if card.get("name") == popular_name), None) if popular_name else None
    practical = popular or best(lambda card: (
        -card_final_level(card),
        0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
        card.get("workCount", 99),
        0 if card.get("ownedCount") else 1,
        card.get("name", ""),
    ))
    def best_for_sizes(sizes: set[str]) -> dict | None:
        pool = [card for card in pick_pool if card.get("size") in sizes]
        return sorted(pool, key=lambda card: (
            -card_final_level(card),
            -as_int(card.get("selectedLevel")),
            card.get("workCount", 99),
            0 if card.get("ownedCount") else 1,
            SIZE_ORDER.get(card.get("size"), 99),
            card.get("name", ""),
        ))[0] if pool else None
    dark_pool = [card for card in pick_pool if any("dark" == str(type_name).lower() for type_name in card.get("types", []))]

    specs = [
        ("recommended", "Recommended", "Common practical choice for this work skill." if popular else "Best practical mix of final level, footprint, focus, and ownership.", practical),
        ("dark", "Best Dark", "Best dark-type option for this work skill; dark Pals do not need Insomnia for night uptime.", sorted(dark_pool, key=lambda card: (
            -card_final_level(card),
            -as_int(card.get("selectedLevel")),
            0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
            card.get("workCount", 99),
            0 if card.get("ownedCount") else 1,
            card.get("name", ""),
        ))[0] if dark_pool else None),
        ("xl", "Best XL", "Highest selected work level among XL Pals.", best_for_sizes({"XL"})),
        ("large", "Best L", "Highest selected work level among L Pals.", best_for_sizes({"L"})),
        ("medium", "Best Medium", "Highest selected work level among Medium (M) Pals.", best_for_sizes({"M"})),
        ("small", "Best Small", "Highest selected work level among Small (S) Pals.", best_for_sizes({"S"})),
        ("xs", "Best XS", "Highest selected work level among Extra Small (XS) Pals.", best_for_sizes({"XS"})),
    ]
    seen = set()
    recommendations = []
    for role, title, reason, card in specs:
        if not card:
            continue
        recommendations.append({
            "role": role,
            "title": title,
            "reason": reason,
            "card": card,
            "duplicate": card.get("name") in seen,
        })
        seen.add(card.get("name"))
    return recommendations


def _work_card_metadata(pal: dict, entries: list[dict], source: dict | None, *, fallback_name: str = "") -> dict:
    name = pal.get("name", fallback_name)
    size = pal_size_for(name)
    return {
        "key": pal.get("key", ""),
        "name": name,
        "types": pal.get("types", []),
        "icon": icon_url_for_key(pal.get("key", "")),
        "size": size,
        "sizeGroup": SIZE_GROUPS.get(size, "Unknown Size"),
        "sizeKnown": size != "Unknown",
        "work": entries,
        "workCount": len(entries),
        "workCondensationSource": "verified" if source else "projected",
        "workCondensationSourceDetail": (source or {}).get("source", ""),
        "workCondensationSourceUrl": (source or {}).get("url", ""),
        "breedable": bool(pal.get("breedable", True)),
        "uniqueOnly": bool(pal.get("uniqueOnly", False)),
    }


def work_suitability_payload(owner: str = "", selected_work: str = "", include_self_breeders: bool = True) -> dict:
    if selected_work not in WORK_LABELS:
        return {
            "error": "Choose a work skill.",
            "groups": [],
            "recommendations": [],
            "selectedWork": "",
            "selectedWorkLabel": "",
            "total": 0,
            "verifiedCondensationCount": 0,
        }
    counts = owned_species_counts(owner)
    cards = []
    for pal in STORE.breeding_data.get("pals", []):
        work = work_for_pal(pal)
        level = as_int(work.get(selected_work))
        if level <= 0:
            continue
        name = pal.get("name", "")
        entries = work_entries(work, name)
        condensed_levels = fully_condensed_work_levels(work, name)
        projected_levels = projected_fully_condensed_work_levels(work)
        work_source = work_source_for(name)
        requires_seed = requires_owned_seed_for_breeding(pal.get("key", ""))
        owned_count = counts.get(name, 0)
        cards.append({
            **_work_card_metadata(pal, entries, work_source),
            "selectedWork": selected_work,
            "selectedWorkLabel": WORK_LABELS[selected_work],
            "selectedLevel": level,
            "selectedFullyCondensedLevel": condensed_levels.get(selected_work),
            "selectedProjectedFullyCondensedLevel": projected_levels.get(selected_work),
            "ownedCount": owned_count,
            "requiresOwnedSeed": requires_seed,
            "unavailableReason": f"It looks like you need to tame or capture {name} first. Once you own one, come back and self-breed it." if requires_seed and not owned_count else "",
        })
    if not include_self_breeders:
        cards = [card for card in cards if not card["requiresOwnedSeed"]]
    cards.sort(key=lambda item: (
        SIZE_ORDER.get(item["size"], 99),
        -card_final_level(item),
        -as_int(item.get("selectedLevel")),
        item["workCount"],
        0 if item.get("ownedCount") else 1,
        item["name"],
    ))
    grouped: dict[str, list[dict]] = {}
    for card in cards:
        grouped.setdefault(card["sizeGroup"], []).append(card)
    group_order = ["Extra Small", "Small", "Medium", "Large", "Extra Large", "Unknown Size"]
    groups = [
        {"title": title, "cards": grouped.get(title, [])}
        for title in group_order
        if grouped.get(title)
    ]
    return {
        "workTypes": [{"key": key, "label": label} for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1])],
        "selectedWork": selected_work,
        "selectedWorkLabel": WORK_LABELS[selected_work],
        "owner": owner,
        "groups": groups,
        "recommendations": work_recommendations(cards, selected_work, include_self_breeders=include_self_breeders),
        "includeSelfBreeders": include_self_breeders,
        "total": len(cards),
        "knownSizeCount": sum(1 for card in cards if card["sizeKnown"]),
        "verifiedCondensationCount": sum(1 for card in cards if card["workCondensationSource"] == "verified"),
        "condensationNote": "Work Suitability uses Palpedia.net base and condenser-star data when available. Missing species fall back to bundled base work levels and are marked Needs verification.",
        "sizeSourceNote": "Size uses Palpedia species metadata. Unknown size means the species was missing or had no recognized size in the synced Palpedia data.",
    }


def work_card_for_pal(pal: dict, owner_counts: dict[str, int], selected_work: str = "") -> dict:
    work = work_for_pal(pal)
    name = pal.get("name", "")
    condensed_levels = fully_condensed_work_levels(work, name)
    projected_levels = projected_fully_condensed_work_levels(work)
    work_source = work_source_for(name)
    entries = work_entries(work, name)
    selected_level = as_int(work.get(selected_work)) if selected_work else max((as_int(work.get(k)) for k in WORK_LABELS), default=0)
    return {
        **_work_card_metadata(pal, entries, work_source),
        "selectedWork": selected_work,
        "selectedWorkLabel": WORK_LABELS.get(selected_work, ""),
        "selectedLevel": selected_level,
        "selectedFullyCondensedLevel": condensed_levels.get(selected_work) if selected_work else None,
        "selectedProjectedFullyCondensedLevel": projected_levels.get(selected_work) if selected_work else None,
        "workLevels": {entry["key"]: entry for entry in entries},
        "ownedCount": owner_counts.get(name, 0),
        "requiresOwnedSeed": requires_owned_seed_for_breeding(pal.get("key", "")),
    }


WORK_SPEED_PASSIVE_SCORE = {
    "Demon’s Hand": 90,
    "Remarkable Craftsmanship": 75,
    "Artisan": 50,
    "Work Slave": 30,
    "Lucky": 20,
    "Serious": 20,
    "Conceited": 10,
}


WORK_UPTIME_PASSIVE_SCORE = {
    "Insomnia": 30,
    "Vampiric": 25,
}


BASE_OPERATION_PASSIVE_SCORE = {
    "Mastery of Fasting": 20,
    "Diet Lover": 15,
    "Workaholic": 15,
    "Dainty Eater": 10,
    "Positive Thinker": 10,
    "Heart of the Immovable King": 8,
}


BASE_OPERATION_PASSIVE_PENALTY = {
    "Musclehead": 50,
    "Slacker": 30,
    "Clumsy": 10,
    "Hooligan": 10,
    "Bottomless Stomach": 15,
    "Destructive": 15,
    "Glutton": 10,
    "Unstable": 10,
}


WORK_RANK_PASSIVE_PATTERNS = {
    "kindling": "EmitFlame",
    "watering": "Watering",
    "planting": "Seeding",
    "electric": "GenerateElectricity",
    "handiwork": "Handcraft",
    "gathering": "Collection",
    "mining": "Mining",
    "farming": "MonsterFarm",
    "lumbering": "Deforest",
    "medicine": "ProductMedicine",
    "cooling": "Cool",
    "transporting": "Transport",
}


def pal_data_for_species(name: str) -> dict | None:
    key = STORE.name_to_key.get(normalize_species(name).lower())
    return next((pal for pal in STORE.breeding_data.get("pals", []) if pal.get("key") == key), None)


def passive_work_score_parts(passives: frozenset[str], types: list[str]) -> dict[str, int]:
    type_set = {str(t).lower() for t in types or []}
    is_dark = "dark" in type_set
    direct_speed = sum(WORK_SPEED_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    uptime = 0 if is_dark else sum(WORK_UPTIME_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    operations = sum(BASE_OPERATION_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    harmful = sum(BASE_OPERATION_PASSIVE_PENALTY.get(passive, 0) for passive in passives)
    return {
        "directSpeed": direct_speed,
        "uptime": uptime,
        "operations": operations,
        "harmful": harmful,
        "total": direct_speed + uptime + operations - harmful,
    }


def passive_work_rank_bonus(row: dict[str, str], skill: str) -> int:
    pattern = WORK_RANK_PASSIVE_PATTERNS.get(skill, "")
    if not pattern:
        return 0
    passive_ids = row.get("passive_ids", "") or ""
    return 1 if f"WorkSuitabilityAddRank_{pattern}_1" in passive_ids else 0


def actual_owned_work_levels(row: dict[str, str], pal: dict) -> dict[str, int]:
    name = pal.get("name", "")
    base = work_for_pal(pal)
    full = fully_condensed_work_levels(base, name)
    stars = as_int(row.get("condensation_stars"))
    levels = {}
    for key in WORK_LABELS:
        base_level = as_int(base.get(key))
        if base_level <= 0:
            continue
        level = as_int(full.get(key), base_level) if stars >= 4 else base_level
        level += passive_work_rank_bonus(row, key)
        levels[key] = min(10, level)
    return levels


def work_entries_from_levels(levels: dict[str, int], maximum_levels: dict[str, int] | None = None) -> list[dict]:
    maximum_levels = maximum_levels or {}
    entries = []
    for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1]):
        level = as_int(levels.get(key))
        if level <= 0:
            continue
        entries.append({
            "key": key,
            "label": label,
            "level": level,
            "currentOnly": True,
            "fullyCondensedLevel": None,
            "projectedFullyCondensedLevel": None,
            "plannerCurrentLevel": level,
            "plannerMaximumLevel": max(level, as_int(maximum_levels.get(key), level)),
        })
    return entries


def maximum_owned_work_levels(row: dict[str, str], pal: dict) -> dict[str, int]:
    base = work_for_pal(pal)
    full = fully_condensed_work_levels(base, pal.get("name", ""))
    levels = {}
    for key in WORK_LABELS:
        base_level = as_int(base.get(key))
        if base_level <= 0:
            continue
        level = as_int(full.get(key), base_level) + passive_work_rank_bonus(row, key)
        levels[key] = min(10, level)
    return levels


def best_owned_work_levels(owner: str) -> dict[str, dict[str, int]]:
    best: dict[str, dict[str, int]] = {}
    for row in STORE.roster:
        if owner and row.get("owner") != owner:
            continue
        species = normalize_species(row.get("species", ""))
        pal = pal_data_for_species(species)
        if not pal:
            continue
        species_levels = best.setdefault(pal.get("name", species), {})
        for key, level in actual_owned_work_levels(row, pal).items():
            species_levels[key] = max(species_levels.get(key, 0), level)
    return best


def work_card_for_owned_row(row: dict[str, str], *, display_location: str | None = None) -> dict | None:
    """Build a worker card; base-aware callers supply a resolved location label."""
    species = normalize_species(row.get("species", ""))
    pal = pal_data_for_species(species)
    if not pal:
        return None
    levels = actual_owned_work_levels(row, pal)
    if not levels:
        return None
    passives = split_passives(row.get("passives"))
    work_source = work_source_for(pal.get("name", ""))
    entries = work_entries_from_levels(levels, maximum_owned_work_levels(row, pal))
    location = display_location if display_location is not None else (row.get("location", "") or "")
    score_parts = passive_work_score_parts(passives, pal.get("types", []))
    return {
        **_work_card_metadata(pal, entries, work_source, fallback_name=species),
        "selectedWork": "",
        "selectedWorkLabel": "",
        "selectedLevel": max(levels.values(), default=0),
        "workLevels": {entry["key"]: entry for entry in entries},
        "ownedCount": 1,
        "plannerPassives": sorted(passives),
        "plannerPassiveSpeedScore": score_parts["total"],
        "plannerPassiveScoreParts": score_parts,
        "plannerLocation": location,
        "plannerCondensationStars": as_int(row.get("condensation_stars")),
        "plannerLevel": as_int(row.get("level")),
        "plannerGender": row.get("gender", ""),
        "plannerInstanceId": row.get("instance_id", ""),
        "rightNow": True,
    }


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "Work suitability and owned worker scoring are available."}
