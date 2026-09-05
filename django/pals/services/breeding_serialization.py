"""Breeding tree and result-group serialization."""

from __future__ import annotations

from .bases import display_owned_location
from .breeding_progress import progress_notes, progress_score, progress_sort_key
from .breeding_state import (
    State,
    result_sort_key,
    substitute_storage_leaves,
    target_complete,
    tree_signature,
)
from .work import icon_url_for_key, species_types_for_key


def unique_serialized(states: list[State], target: frozenset[str], allowed: frozenset[str], limit: int, *, fastest: bool = False, iv_preference: str = "none", progress_species_set: set[str] | None = None, intended_gender: str = "any", replacement_pool: list[State] | None = None) -> list[dict]:
    out = []
    seen: set[tuple] = set()
    progress_species_set = progress_species_set or set()
    if progress_species_set:
        ordered = sorted(states, key=lambda x: progress_sort_key(x, target, allowed, progress_species_set, iv_preference=iv_preference))
    else:
        ordered = sorted(states, key=lambda x: result_sort_key(x, target, allowed, fastest=fastest, iv_preference=iv_preference))
    for s in ordered:
        key = tree_signature(s)
        if key in seen:
            continue
        seen.add(key)
        item_state = substitute_storage_leaves(s, replacement_pool, target, allowed) if replacement_pool else s
        item = serialize_state(item_state, target, allowed, intended_gender, iv_preference)
        if progress_species_set:
            item["progressScore"] = progress_score(s, target, allowed, progress_species_set)
            item["progressNotes"] = progress_notes(s, target, allowed)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def build_group(slug: str, title: str, description: str, states: list[State], target_key: str, target: frozenset[str], allowed: frozenset[str], *, fastest: bool = False, complete_only: bool = True, iv_preference: str = "none", intended_gender: str = "any", replacement_pool: list[State] | None = None) -> dict:
    matches = [s for s in states if s.species_key == target_key]
    if complete_only:
        matches = [s for s in matches if target_complete(s, target)]
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "results": unique_serialized(matches, target, allowed, 6, fastest=fastest, iv_preference=iv_preference, intended_gender=intended_gender, replacement_pool=replacement_pool),
    }


def cake_recommendation(target: frozenset[str], iv_preference: str = "none") -> tuple[str, str]:
    if target:
        return "Special Cake", "Best fit when trying to inherit multiple prepared passive skills."
    if iv_preference in {"highest_iv", "highest_attack"}:
        return "Mushroom Cake", "Best fit when the breeding goal is stronger newborn stats."
    return "Cake", "Baseline cake for producing the planned child species."


def opposite_gender(gender: str) -> str:
    if gender == "Male":
        return "Female"
    if gender == "Female":
        return "Male"
    return "any"


def concrete_gender(s: State, intended_gender: str = "any") -> str:
    if intended_gender in {"Male", "Female"}:
        return intended_gender
    if s.gender in {"Male", "Female"}:
        return s.gender
    return "any"


def ordered_parent_specs(a: State, b: State) -> list[tuple[State, str]]:
    a_intended = opposite_gender(concrete_gender(b))
    b_intended = opposite_gender(concrete_gender(a))
    specs = [(a, a_intended), (b, b_intended)]
    order = {"Male": 0, "Female": 1}
    return sorted(specs, key=lambda item: (order.get(concrete_gender(item[0], item[1]), 2), item[0].species, item[0].label))


def serialize_state(s: State, target: frozenset[str], allowed: frozenset[str], intended_gender: str = "any", iv_preference: str = "none") -> dict:
    display_gender = concrete_gender(s, intended_gender)
    if display_gender == "any":
        display_gender = s.gender
    cake_type, cake_reason = cake_recommendation(target, iv_preference)
    parent_items = []
    if s.parents:
        parent_items = [
            serialize_state(parent, target, allowed, parent_intended, iv_preference)
            for parent, parent_intended in ordered_parent_specs(s.parents[0], s.parents[1])
        ]
    location = display_owned_location(s.location)
    return {
        "species": s.species,
        "gender": s.gender,
        "displayGender": display_gender,
        "intendedGender": intended_gender if intended_gender in {"Male", "Female"} else "",
        "steps": s.steps,
        "breedCount": s.breed_count,
        "suggestedCakes": s.breed_count,
        "suggestedCakeType": cake_type if s.breed_count else "",
        "cakeReason": cake_reason if s.breed_count else "",
        "hpIv": round(s.avg_hp_iv, 1),
        "attackIv": round(s.avg_attack_iv, 1),
        "defenseIv": round(s.avg_defense_iv, 1),
        "avgIv": round(s.avg_iv, 1),
        "avgAttackIv": round(s.avg_attack_iv, 1),
        "passives": sorted(s.passives),
        "desired": sorted(s.passives & target),
        "junk": sorted(s.passives - target - allowed),
        "missing": sorted(target - s.passives),
        "allowed": sorted(s.passives & allowed),
        "label": s.label,
        "location": location,
        "box": s.box,
        "slot": s.slot,
        "baseSlot": s.base_slot,
        "icon": icon_url_for_key(s.species_key),
        "types": species_types_for_key(s.species_key),
        "parents": parent_items,
    }
