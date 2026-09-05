"""Ranch drop discovery and candidate recommendations."""

from __future__ import annotations

import re

from .data import STORE, as_int
from .work import owned_species_counts, work_card_for_pal, work_for_pal


def normalized_item_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def ranch_drop_names_for_pal(pal: dict) -> set[str]:
    work = work_for_pal(pal)
    if as_int(work.get("farming")) <= 0:
        return set()
    partner = pal.get("partnerSkill") or {}
    desc = str(partner.get("desc") or "")
    desc_key = normalized_item_text(desc)
    desc_lower = desc.lower()
    if "ranch" not in desc_lower:
        return set()
    drops = [drop for drop in (pal.get("drops") or []) if isinstance(drop, dict) and drop.get("name")]
    names = {drop.get("name", "") for drop in drops}
    found = {name for name in names if normalized_item_text(name) and normalized_item_text(name) in desc_key}
    if "variousseeds" in desc_key:
        found.update(name for name in names if "seed" in name.lower())
    if "mushroomorcavernmushroom" in desc_key:
        found.update(name for name in names if "mushroom" in name.lower())
    if "laysanegg" in desc_key:
        found.update(name for name in names if normalized_item_text(name) == "egg")
    if "itemsfromtheground" in desc_key:
        found.update(names)
    return found


def ranch_drops_payload(owner: str = "", include_self_breeders: bool = True) -> dict:
    counts = owned_species_counts(owner)
    items: dict[str, dict] = {}
    pal_count = 0
    for pal in STORE.breeding_data.get("pals", []):
        ranch_names = ranch_drop_names_for_pal(pal)
        if not ranch_names:
            continue
        pal_count += 1
        card = work_card_for_pal(pal, counts, "farming")
        partner = pal.get("partnerSkill") or {}
        card["ranchDrops"] = [
            drop for drop in (pal.get("drops") or [])
            if isinstance(drop, dict) and drop.get("name") in ranch_names
        ]
        card["partnerSkill"] = {
            "name": partner.get("name", ""),
            "desc": partner.get("desc", ""),
        }
        for drop in card["ranchDrops"]:
            name = drop.get("name", "")
            if not name:
                continue
            bucket = items.setdefault(name, {"name": name, "pals": []})
            bucket["pals"].append(card)

    def pal_sort_key(card: dict):
        return (
            0 if card.get("ownedCount") else 1,
            -as_int(card.get("selectedFullyCondensedLevel") or card.get("selectedLevel")),
            0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
            card.get("workCount", 99),
            card.get("name", ""),
        )

    results = []
    for item in items.values():
        pals = sorted(item["pals"], key=pal_sort_key)
        pick_pool = pals if include_self_breeders else [card for card in pals if not card.get("requiresOwnedSeed")]
        pick_pool = pick_pool or pals
        results.append({
            "name": item["name"],
            "count": len(pals),
            "best": pick_pool[0] if pick_pool else None,
            "pals": pals,
        })
    results.sort(key=lambda item: item["name"])
    return {
        "owner": owner,
        "items": results,
        "includeSelfBreeders": include_self_breeders,
        "totalItems": len(results),
        "totalPals": pal_count,
        "sourceNote": "Ranch Drops uses Pals with Farming suitability and partner-skill text that mentions assignment to a Ranch. Item names are matched from the Pal's bundled drops only when the ranch text names or implies that item.",
    }


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "Ranch drops and candidate recommendations are available."}
