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
from .data import IMPLANT_INVENTORY_FILE, STORE, as_bool, as_int, canonical_passives
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


def iv_goal_score(s: State, goal: str) -> tuple:
    if goal == "attack":
        return (s.avg_attack_iv, s.avg_iv, s.avg_hp_iv, s.avg_defense_iv)
    if goal == "survival":
        return ((s.avg_hp_iv + s.avg_defense_iv) / 2, s.avg_hp_iv, s.avg_defense_iv, s.avg_attack_iv)
    if goal == "highest":
        return (s.avg_iv, s.avg_attack_iv, s.avg_hp_iv, s.avg_defense_iv)
    weakest = min(s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv)
    return (weakest, s.avg_iv, s.avg_attack_iv, s.avg_hp_iv, s.avg_defense_iv)


def iv_goal_pair_score(a: State, b: State, goal: str) -> tuple:
    max_hp = max(a.avg_hp_iv, b.avg_hp_iv)
    max_attack = max(a.avg_attack_iv, b.avg_attack_iv)
    max_defense = max(a.avg_defense_iv, b.avg_defense_iv)
    coverage_avg = (max_hp + max_attack + max_defense) / 3
    parent_avg = (a.avg_iv + b.avg_iv) / 2
    if goal == "attack":
        return (max_attack, coverage_avg, parent_avg, max_hp, max_defense)
    if goal == "survival":
        return ((max_hp + max_defense) / 2, max_hp, max_defense, max_attack, coverage_avg, parent_avg)
    if goal == "highest":
        return (coverage_avg, parent_avg, max_attack, max_hp, max_defense)
    weakest = min(max_hp, max_attack, max_defense)
    return (weakest, coverage_avg, parent_avg, max_attack, max_hp, max_defense)


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


def serialize_iv_pal(s: State, target: frozenset[str], allowed: frozenset[str]) -> dict:
    location = display_owned_location(s.location)
    selection_id = s.instance_id or f"{s.species_key}|{s.gender}|{s.location}|{s.box}|{s.slot}|{s.label}"
    return {
        "instanceId": s.instance_id,
        "selectionId": selection_id,
        "species": s.species,
        "gender": s.gender,
        "passives": sorted(s.passives),
        "desired": sorted(s.passives & target),
        "junk": sorted(s.passives - target - allowed),
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


def serialize_iv_pair(a: State, b: State, target: frozenset[str], required: frozenset[str], allowed: frozenset[str]) -> dict:
    pool = frozenset(set(a.passives) | set(b.passives))
    best_hp = max(a.avg_hp_iv, b.avg_hp_iv)
    best_attack = max(a.avg_attack_iv, b.avg_attack_iv)
    best_defense = max(a.avg_defense_iv, b.avg_defense_iv)
    support = iv_100_support(a, b)
    return {
        "parents": [serialize_iv_pal(a, target, allowed), serialize_iv_pal(b, target, allowed)],
        "desired": sorted(pool & target),
        "missing": sorted(required - pool),
        "junk": sorted(pool - target - allowed),
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
        "clean": not (pool - target - allowed),
        "compatible": compatible(a, b),
    }


def improves_selected_iv(candidate: State, selected: State) -> bool:
    return (
        candidate.avg_hp_iv > selected.avg_hp_iv
        or candidate.avg_attack_iv > selected.avg_attack_iv
        or candidate.avg_defense_iv > selected.avg_defense_iv
    )


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
    if not target:
        return {"error": "Choose the passives you want before calculating perfect IV pairs."}
    if len(target) > 4:
        return {"error": "A Pal can only have 4 final passives."}
    implant_passives &= target
    allowed = allowed_extras | implant_passives
    natural_target = frozenset(target - implant_passives)
    owned = owned_states_for_owner(owner)
    species_states = [s for s in owned if s.species_key == target_key]
    matching = [
        s
        for s in species_states
        if natural_target <= s.passives and not (s.passives - target - allowed)
    ]
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
        if not compatible(a, b):
            continue
        if not gender_matches(a, gender_preference) and not gender_matches(b, gender_preference) and gender_preference not in {"", "any", "Any", None}:
            continue
        pool = frozenset(set(a.passives) | set(b.passives))
        missing = natural_target - pool
        junk = pool - target - allowed
        covered, doubled, single, backup = iv_100_score(a, b)
        parent_desired_count = len(a.passives & target) + len(b.passives & target)
        parent_avg = (a.avg_iv + b.avg_iv) / 2
        pairs.append((
            (len(missing), len(junk), -(covered), -(doubled), single, -parent_desired_count, -backup, -parent_avg, a.label, b.label),
            a,
            b,
        ))
    pairs.sort(key=lambda item: item[0])
    serialized_pairs = []
    seen = set()
    for _, a, b in pairs:
        sig = tuple(sorted((a.label, b.label)))
        if sig in seen:
            continue
        seen.add(sig)
        serialized_pairs.append(serialize_iv_pair(a, b, target, natural_target, allowed))
        if len(serialized_pairs) >= 12:
            break

    perfect_matching = [
        s
        for s in ranked_matching
        if round(s.avg_hp_iv) >= 100 and round(s.avg_attack_iv) >= 100 and round(s.avg_defense_iv) >= 100
    ]
    alpha_only = None
    if require_alpha and perfect_matching:
        owned_match = next((s for s in perfect_matching if not s.is_alpha), perfect_matching[0])
        missing = [] if owned_match.is_alpha else ["Alpha"]
        clean_parent_pairs = [pair for pair in serialized_pairs if pair.get("clean") and not pair.get("missing")]
        alpha_only = {
            "state": "complete" if owned_match.is_alpha else "missing_alpha",
            "title": "Target complete" if owned_match.is_alpha else "Target already solved except Alpha",
            "message": (
                f"You own an Alpha {STORE.pals[target_key].name} with the exact passives and 100/100/100 IVs."
                if owned_match.is_alpha
                else f"You own a {STORE.pals[target_key].name} with the exact passives and 100/100/100 IVs. Only an Alpha version is remaining."
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
