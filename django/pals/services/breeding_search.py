"""Bounded breeding search and final parent routes."""

from __future__ import annotations

from itertools import combinations, product

from .breeding_state import (
    State,
    compact_states,
    compatible,
    result_sort_key,
    state_score,
)
from .data import STORE


def missing_passive_sources(owned: list[State], target_key: str, target: frozenset[str]) -> dict:
    """Prove missing inheritance sources using the full species ancestry graph.

    Presence is only a necessary condition: gender, partner ownership, and search
    limits can still prevent a route. Absence proves no owned inheritance route.
    """
    ancestors = {target_key}
    pending = [target_key]
    while pending:
        for pair in STORE.parent_pairs_for_child(pending.pop()):
            for key in pair:
                if key not in ancestors:
                    ancestors.add(key)
                    pending.append(key)
    available = frozenset(p for s in owned if s.species_key in ancestors for p in s.passives)
    return {
        "missingPassives": sorted(target - available),
        "sourceSpecies": sorted(STORE.pals[key].name for key in ancestors),
    }


def search_states(
    owned: list[State],
    target: frozenset[str],
    allowed: frozenset[str],
    *,
    strict: bool,
    max_steps: int,
    per_species: int,
    global_limit: int,
    iv_preference: str = "none",
) -> list[State]:
    seed = [s for s in owned if not strict or not (s.passives - target - allowed)]
    states = compact_states(seed, target, allowed, per_species=per_species, iv_preference=iv_preference)
    all_states = list(states)
    seen = {s.id for s in all_states}

    for depth in range(1, max_steps + 1):
        new_states: list[State] = []
        source = sorted(all_states, key=lambda s: state_score(s, target, allowed, iv_preference))[:global_limit]
        for a, b in combinations(source, 2):
            if not compatible(a, b):
                continue
            child = STORE.child_for(a.species_key, b.species_key)
            if not child:
                continue
            pool = frozenset(set(a.passives) | set(b.passives))
            if strict and (pool - target - allowed):
                continue
            child_name = STORE.pals[child].name
            s = State(
                species_key=child,
                species=child_name,
                passives=pool,
                gender="Either",
                steps=max(a.steps, b.steps) + 1,
                breed_count=a.breed_count + b.breed_count + 1,
                hp_iv=a.hp_iv + b.hp_iv,
                attack_iv=a.attack_iv + b.attack_iv,
                defense_iv=a.defense_iv + b.defense_iv,
                iv_total=a.iv_total + b.iv_total,
                iv_sources=a.iv_sources + b.iv_sources,
                label=f"Breed {child_name}",
                location="bred intermediate",
                box=None,
                slot=None,
                base_workers_used=a.base_workers_used + b.base_workers_used,
                parents=(a, b),
            )
            if s.id not in seen:
                seen.add(s.id)
                new_states.append(s)
        if not new_states:
            continue
        all_states = compact_states(all_states + new_states, target, allowed, per_species=per_species, iv_preference=iv_preference)
    return all_states


def top_donors_for_species(states: list[State], species_key: str, target: frozenset[str], allowed: frozenset[str], limit: int = 10, iv_preference: str = "none") -> list[State]:
    candidates = [s for s in states if s.species_key == species_key]
    candidates.sort(key=lambda s: result_sort_key(s, target, allowed, iv_preference=iv_preference))
    out: list[State] = []
    seen: set[tuple] = set()
    for s in candidates:
        key = (tuple(sorted(s.passives)), s.steps, s.breed_count, s.gender, s.label)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def final_parent_routes(states: list[State], target_key: str, target: frozenset[str], allowed: frozenset[str], limit: int = 180, iv_preference: str = "none") -> list[State]:
    routes: list[State] = []
    child_name = STORE.pals[target_key].name
    pairs = STORE.parent_pairs_for_child(target_key)
    donor_cache: dict[str, list[State]] = {}

    def donors_for(key: str) -> list[State]:
        if key not in donor_cache:
            donor_cache[key] = top_donors_for_species(states, key, target, allowed, iv_preference=iv_preference)
        return donor_cache[key]

    for left_key, right_key in pairs:
        left = donors_for(left_key)
        right = donors_for(right_key)
        if not left or not right:
            continue
        if left_key == right_key:
            pair_source = combinations(left, 2)
        else:
            pair_source = product(left, right)
        for a, b in pair_source:
            if a is b or not compatible(a, b):
                continue
            pool = frozenset(set(a.passives) | set(b.passives))
            route = State(
                species_key=target_key,
                species=child_name,
                passives=pool,
                gender="Either",
                steps=max(a.steps, b.steps) + 1,
                breed_count=a.breed_count + b.breed_count + 1,
                hp_iv=a.hp_iv + b.hp_iv,
                attack_iv=a.attack_iv + b.attack_iv,
                defense_iv=a.defense_iv + b.defense_iv,
                iv_total=a.iv_total + b.iv_total,
                iv_sources=a.iv_sources + b.iv_sources,
                label=f"Breed {child_name} via {STORE.pals[left_key].name} + {STORE.pals[right_key].name}",
                location="final parent route",
                box=None,
                slot=None,
                base_workers_used=a.base_workers_used + b.base_workers_used,
                parents=(a, b),
            )
            routes.append(route)

    routes.sort(key=lambda s: result_sort_key(s, target, allowed, iv_preference=iv_preference))
    return routes[:limit]
