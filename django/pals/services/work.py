"""Species metadata and work suitability recommendations."""

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
        size = pal_size_for(name)
        entries = work_entries(work, name)
        condensed_levels = fully_condensed_work_levels(work, name)
        projected_levels = projected_fully_condensed_work_levels(work)
        work_source = work_source_for(name)
        requires_seed = requires_owned_seed_for_breeding(pal.get("key", ""))
        owned_count = counts.get(name, 0)
        cards.append({
            "key": pal.get("key", ""),
            "name": name,
            "types": pal.get("types", []),
            "icon": icon_url_for_key(pal.get("key", "")),
            "size": size,
            "sizeGroup": SIZE_GROUPS.get(size, "Unknown Size"),
            "sizeKnown": size != "Unknown",
            "selectedWork": selected_work,
            "selectedWorkLabel": WORK_LABELS[selected_work],
            "selectedLevel": level,
            "selectedFullyCondensedLevel": condensed_levels.get(selected_work),
            "selectedProjectedFullyCondensedLevel": projected_levels.get(selected_work),
            "work": entries,
            "workCount": len(entries),
            "workCondensationSource": "verified" if work_source else "projected",
            "workCondensationSourceDetail": (work_source or {}).get("source", ""),
            "workCondensationSourceUrl": (work_source or {}).get("url", ""),
            "ownedCount": owned_count,
            "breedable": bool(pal.get("breedable", True)),
            "uniqueOnly": bool(pal.get("uniqueOnly", False)),
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


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "Work suitability data and recommendations are available."}
