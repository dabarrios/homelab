"""IV planning and implant inventory helpers."""

from __future__ import annotations

import json

from itertools import combinations

from .bases import display_owned_location
from .breeding_state import (
    State,
    compatible,
    gender_filtered,
    gender_matches,
    owned_states_for_owner,
)
from .data import IMPLANT_INVENTORY_FILE, ITEM_INVENTORY_FILE, STORE, as_bool, as_int, canonical_passives
from .work import icon_url_for_key


def load_implant_inventory() -> dict:
    if not IMPLANT_INVENTORY_FILE.exists():
        return {}
    try:
        data = json.loads(IMPLANT_INVENTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    inventory = {}
    for passive, item in data.items():
        if not isinstance(item, dict):
            continue
        name = str(passive or "").strip()
        if not name:
            continue
        inventory[name] = {
            "infinite": bool(item.get("infinite")),
            "count": max(0, as_int(item.get("count"))) if not item.get("infinite") else None,
        }
    return inventory


def available_implant_passives() -> set[str]:
    return {
        passive
        for passive, item in load_implant_inventory().items()
        if item.get("infinite") or as_int(item.get("count")) > 0
    }


def save_implant_inventory(inventory: dict) -> None:
    IMPLANT_INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMPLANT_INVENTORY_FILE.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")


def load_item_inventory() -> dict[str, int]:
    if not ITEM_INVENTORY_FILE.exists():
        return {}
    try:
        data = json.loads(ITEM_INVENTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(name): max(0, as_int(count)) for name, count in data.items()}


def available_gender_reversers() -> int:
    return load_item_inventory().get("Pal Reverser", 0)


def iv_100_support(a: State, b: State) -> dict[str, int]:
    return {
        "hp": int(round(a.avg_hp_iv) >= 100) + int(round(b.avg_hp_iv) >= 100),
        "attack": int(round(a.avg_attack_iv) >= 100) + int(round(b.avg_attack_iv) >= 100),
        "defense": int(round(a.avg_defense_iv) >= 100) + int(round(b.avg_defense_iv) >= 100),
    }


def iv_100_score(a: State, b: State) -> tuple[int, int, int, float]:
    support = iv_100_support(a, b)
    covered = sum(1 for value in support.values() if value > 0)
    doubled = sum(1 for value in support.values() if value > 1)
    single = sum(1 for value in support.values() if value == 1)
    backup = (
        max(a.avg_hp_iv, b.avg_hp_iv)
        + max(a.avg_attack_iv, b.avg_attack_iv)
        + max(a.avg_defense_iv, b.avg_defense_iv)
    ) / 3
    return covered, doubled, single, backup


def gender_change_plan(a: State, b: State, allow_gender_changes: bool, available_reversers: int) -> tuple[tuple[str | None, str | None], list[dict]] | None:
    if compatible(a, b):
        return (None, None), []
    if not allow_gender_changes or available_reversers < 1 or a.gender != b.gender or a.gender not in {"Male", "Female"}:
        return None
    target_gender = "Female" if a.gender == "Male" else "Male"
    # Either parent can be converted; use the lower-IV parent deterministically
    # so the stronger parent remains untouched when the pair is presented.
    swap_first = (a.avg_iv, a.label) <= (b.avg_iv, b.label)
    changed, unchanged = (a, b) if swap_first else (b, a)
    changed_target = "Female" if changed.gender == "Male" else "Male"
    changes = [{
        "selectionId": changed.instance_id or changed.label,
        "label": changed.label,
        "from": changed.gender,
        "to": changed_target,
        "item": "Pal Reverser",
    }]
    planned = (changed_target, None) if swap_first else (None, changed_target)
    return planned, changes


def serialize_iv_pal(s: State, target: frozenset[str], allowed: frozenset[str], planned_gender: str | None = None) -> dict:
    location = display_owned_location(s.location)
    selection_id = s.instance_id or f"{s.species_key}|{s.gender}|{s.location}|{s.box}|{s.slot}|{s.label}"
    passive_agnostic = not target
    return {
        "instanceId": s.instance_id,
        "selectionId": selection_id,
        "species": s.species,
        "gender": s.gender,
        "displayGender": planned_gender or s.gender,
        "plannedGender": planned_gender or "",
        "genderChange": bool(planned_gender and planned_gender != s.gender),
        "passives": sorted(s.passives),
        "desired": sorted(s.passives & target),
        "junk": sorted(s.passives - target - allowed) if not passive_agnostic else [],
        "missing": sorted(target - s.passives),
        "hpIv": round(s.avg_hp_iv, 1),
        "attackIv": round(s.avg_attack_iv, 1),
        "defenseIv": round(s.avg_defense_iv, 1),
        "avgIv": round(s.avg_iv, 1),
        "label": s.label,
        "location": location,
        "box": s.box,
        "slot": s.slot,
        "baseSlot": s.base_slot,
        "icon": icon_url_for_key(s.species_key),
        "isAlpha": s.is_alpha,
    }


def serialize_iv_pair(a: State, b: State, target: frozenset[str], required: frozenset[str], allowed: frozenset[str], planned_genders: tuple[str | None, str | None] = (None, None), gender_changes: list[dict] | None = None, effective_compatible: bool | None = None) -> dict:
    pool = frozenset(set(a.passives) | set(b.passives))
    passive_agnostic = not target
    best_hp = max(a.avg_hp_iv, b.avg_hp_iv)
    best_attack = max(a.avg_attack_iv, b.avg_attack_iv)
    best_defense = max(a.avg_defense_iv, b.avg_defense_iv)
    support = iv_100_support(a, b)
    return {
        "parents": [serialize_iv_pal(a, target, allowed, planned_genders[0]), serialize_iv_pal(b, target, allowed, planned_genders[1])],
        "desired": sorted(pool & target),
        "missing": sorted(required - pool),
        "junk": sorted(pool - target - allowed) if not passive_agnostic else [],
        "passivePool": sorted(pool),
        "bestHpIv": round(best_hp, 1),
        "bestAttackIv": round(best_attack, 1),
        "bestDefenseIv": round(best_defense, 1),
        "bestAvgIv": round((best_hp + best_attack + best_defense) / 3, 1),
        "parentAvgIv": round((a.avg_iv + b.avg_iv) / 2, 1),
        "goalScore": round((best_hp + best_attack + best_defense) / 3, 1),
        "hp100Support": support["hp"],
        "attack100Support": support["attack"],
        "defense100Support": support["defense"],
        "perfectCoverage": sum(1 for value in support.values() if value > 0),
        "doublePerfectCoverage": sum(1 for value in support.values() if value > 1),
        "clean": passive_agnostic or not (pool - target - allowed),
        "compatible": compatible(a, b) if effective_compatible is None else effective_compatible,
        "genderChangeCount": len(gender_changes or []),
        "genderChanges": gender_changes or [],
    }


def build_iv_plan(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"error": f"Unknown target species: {target_name}"}
    implant_passives = canonical_passives(payload.get("implantPassives", []))
    allowed_extras = canonical_passives(payload.get("allowedExtras", []))
    gender_preference = payload.get("genderPreference") or "any"
    require_alpha = as_bool(payload.get("requireAlpha"))
    target = canonical_passives(payload.get("passives", []))
    allow_gender_changes = as_bool(payload.get("allowGenderChanges"))
    available_reversers = available_gender_reversers()
    if len(target) > 4:
        return {"error": "A Pal can only have 4 final passives."}
    implant_passives &= target
    allowed = allowed_extras | implant_passives
    natural_target = frozenset(target - implant_passives)
    owned = owned_states_for_owner(owner)
    species_states = [s for s in owned if s.species_key == target_key]
    matching = (
        list(species_states)
        if not target
        else [
            s
            for s in species_states
            if natural_target <= s.passives and not (s.passives - target - allowed)
        ]
    )
    matching_gender = gender_filtered(matching, gender_preference)
    rank_pool = matching_gender or matching
    ranked_matching = sorted(
        rank_pool,
        key=lambda s: (
            -sum(1 for value in (s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv) if round(value) >= 100),
            -s.avg_iv,
            s.label,
        ),
    )

    pairs = []
    for a, b in combinations(species_states, 2):
        gender_plan = gender_change_plan(a, b, allow_gender_changes, available_reversers)
        if gender_plan is None:
            continue
        planned_genders, gender_changes = gender_plan
        effective_genders = (planned_genders[0] or a.gender, planned_genders[1] or b.gender)
        if gender_preference not in {"", "any", "Any", None} and not any(gender == gender_preference or gender == "Either" for gender in effective_genders):
            continue
        pool = frozenset(set(a.passives) | set(b.passives))
        missing = natural_target - pool
        junk = pool - target - allowed if target else frozenset()
        covered, doubled, single, backup = iv_100_score(a, b)
        parent_desired_count = len(a.passives & target) + len(b.passives & target) if target else 0
        parent_avg = (a.avg_iv + b.avg_iv) / 2
        pairs.append((
            (len(missing), len(junk), len(gender_changes), -(covered), -(doubled), single, -parent_desired_count, -backup, -parent_avg, a.label, b.label),
            a,
            b,
            planned_genders,
            gender_changes,
        ))
    pairs.sort(key=lambda item: item[0])
    serialized_pairs = []
    seen = set()
    for _, a, b, planned_genders, gender_changes in pairs:
        sig = tuple(sorted((a.label, b.label)))
        if sig in seen:
            continue
        seen.add(sig)
        serialized_pairs.append(serialize_iv_pair(a, b, target, natural_target, allowed, planned_genders, gender_changes, True))
        if len(serialized_pairs) >= 12:
            break

    perfect_matching = [
        s
        for s in ranked_matching
        if round(s.avg_hp_iv) >= 100 and round(s.avg_attack_iv) >= 100 and round(s.avg_defense_iv) >= 100
    ]
    alpha_only = None
    if require_alpha and perfect_matching:
        owned_match = next((s for s in perfect_matching if s.is_alpha), perfect_matching[0])
        missing = [] if owned_match.is_alpha else ["Alpha"]
        clean_parent_pairs = [pair for pair in serialized_pairs if pair.get("clean") and not pair.get("missing")]
        alpha_only = {
            "state": "complete" if owned_match.is_alpha else "missing_alpha",
            "title": "Target complete" if owned_match.is_alpha else "Target already solved except Alpha",
            "message": (
                f"You own an Alpha {STORE.pals[target_key].name} with 100/100/100 IVs."
                if owned_match.is_alpha
                else f"You own a {STORE.pals[target_key].name} with 100/100/100 IVs. Only an Alpha version is remaining."
            ),
            "missing": missing,
            "ownedMatch": serialize_iv_pal(owned_match, target, allowed),
            "cleanParentPool": bool(clean_parent_pairs),
            "parentPoolWarning": not bool(clean_parent_pairs),
            "recommendedCake": "Special Cake",
            "recommendedCakeReason": "Use it when the breeding pair's combined passive pool is exactly the target passives.",
            "eggPickup": "Broncherry + Broncherry Aqua",
            "nextSteps": [
                {
                    "title": "Use Special Cake",
                    "detail": "Locks the passive result when the parent passive pool is clean.",
                    "icon": "cake-slice",
                    "primary": True,
                },
                {
                    "title": "Repeat Hatch",
                    "detail": f"Keep breeding this pair until an Alpha {STORE.pals[target_key].name} hatches.",
                    "icon": "egg",
                    "primary": False,
                },
                {
                    "title": "Egg Pickup",
                    "detail": "Pick up eggs with fully condensed Broncherry + Broncherry Aqua for guaranteed Alpha eggs.",
                    "icon": "package-open",
                    "primary": False,
                },
            ],
        }

    return {
        "mode": "iv",
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "requireAlpha": require_alpha,
        "alphaOnly": alpha_only,
        "requestedPassives": sorted(target),
        "naturalPassives": sorted(natural_target),
        "implantPassives": sorted(implant_passives),
        "allowedExtras": sorted(allowed),
        "genderPreference": gender_preference,
        "allowGenderChanges": allow_gender_changes,
        "availableGenderReversers": available_reversers,
        "ivGoal": "perfect",
        "ownedCount": len(owned),
        "targetCount": len(species_states),
        "matchingCount": len(matching),
        "matchingGenderCount": len(matching_gender),
        "matchingPals": [serialize_iv_pal(s, target, allowed) for s in ranked_matching[:24]],
        "pairs": serialized_pairs,
    }


def owned_target_pals_payload(owner: str, target_name: str) -> dict:
    owner_key = (owner or "David").lower()
    target_key = STORE.name_to_key.get((target_name or "").strip().lower())
    if not target_key:
        return {"ok": False, "error": f"Unknown target species: {target_name}"}
    owned = owned_states_for_owner(owner_key)
    species_states = [s for s in owned if s.species_key == target_key]
    target = frozenset()
    allowed = frozenset()
    pals = sorted(
        (serialize_iv_pal(s, target, allowed) for s in species_states),
        key=lambda item: (-len(item["passives"]), -item["avgIv"], item["location"], item["label"]),
    )
    return {
        "ok": True,
        "owner": owner_key,
        "target": STORE.pals[target_key].name,
        "count": len(pals),
        "pals": pals,
    }


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "IV planning and implant inventory are available."}
