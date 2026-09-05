"""Automatic work speed and ranch passive profiles."""

from __future__ import annotations

from dataclasses import replace

from .breeding_search import final_parent_routes, search_states
from .breeding_state import State, gender_filtered, owned_states_for_owner
from .data import STORE
from .work import (
    WORK_SPEED_PASSIVE_SCORE,
    WORK_UPTIME_PASSIVE_SCORE,
    species_types_for_key,
)


def work_speed_profile_scores(include_insomnia: bool = False) -> dict[str, int]:
    scores = dict(WORK_SPEED_PASSIVE_SCORE)
    if include_insomnia:
        scores["Insomnia"] = WORK_UPTIME_PASSIVE_SCORE["Insomnia"]
    return scores


def work_speed_passive_order(passives, scores: dict[str, int] | None = None) -> list[str]:
    scores = scores or WORK_SPEED_PASSIVE_SCORE
    return sorted(
        (passive for passive in passives if passive in scores),
        key=lambda passive: (-scores[passive], passive),
    )


def owned_state_identity(state: State) -> tuple:
    return (
        state.species_key,
        state.gender,
        state.passives,
        state.label,
        state.location,
        state.base_slot,
        state.instance_id,
        state.hp_iv,
        state.attack_iv,
        state.defense_iv,
        state.iv_sources,
    )


def restore_profile_tree(state: State, originals: dict[tuple, State], desired: frozenset[str]) -> State:
    if not state.parents:
        return originals.get(owned_state_identity(state), state)
    parents = (
        restore_profile_tree(state.parents[0], originals, desired),
        restore_profile_tree(state.parents[1], originals, desired),
    )
    pool = frozenset(set(parents[0].passives) | set(parents[1].passives))
    hp_iv = parents[0].hp_iv + parents[1].hp_iv
    attack_iv = parents[0].attack_iv + parents[1].attack_iv
    defense_iv = parents[0].defense_iv + parents[1].defense_iv
    return replace(
        state,
        passives=pool,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=hp_iv + attack_iv + defense_iv,
        iv_sources=parents[0].iv_sources + parents[1].iv_sources,
        base_workers_used=parents[0].base_workers_used + parents[1].base_workers_used,
        parents=parents,
    )


def best_work_speed_profile(
    owned: list[State],
    target_key: str,
    gender_preference: str,
    include_insomnia: bool = False,
    priority_passive_groups: list[list[str]] | None = None,
    implant_passives: set[str] | None = None,
) -> dict:
    target_is_dark = "dark" in {str(t).lower() for t in species_types_for_key(target_key)}
    force_insomnia = include_insomnia and not target_is_dark
    scores = work_speed_profile_scores(force_insomnia)
    selection_scores = dict(scores)
    if force_insomnia and "Lucky" in selection_scores and "Work Slave" in selection_scores:
        selection_scores["Lucky"] = max(selection_scores["Lucky"], selection_scores["Work Slave"] + 1)
    implant_passives = set(implant_passives or set())
    priority_groups = [
        list(dict.fromkeys(passive for passive in group if passive))
        for group in (priority_passive_groups or [])
    ]
    priority_groups = [group for group in priority_groups if group]
    priority_options = [passive for group in priority_groups for passive in group]
    for passive in priority_options:
        scores.setdefault(passive, 0)
    ideal = []
    for group in priority_groups:
        passive = group[0]
        if passive not in ideal:
            ideal.append(passive)
    if force_insomnia:
        ideal.extend(passive for passive in work_speed_passive_order(WORK_SPEED_PASSIVE_SCORE, scores) if passive not in ideal)
        ideal = ideal[:3]
        if "Insomnia" not in ideal:
            ideal.append("Insomnia")
    else:
        ideal.extend(passive for passive in work_speed_passive_order(scores, scores) if passive not in ideal)
        ideal = ideal[:4]
    available = frozenset(
        passive
        for state in owned
        for passive in state.passives
        if passive in scores
    ) | frozenset(passive for passive in implant_passives if passive in scores)
    if not available:
        return {"ideal": ideal, "selected": [], "route": None, "score": 0}

    breeding_available = frozenset(passive for passive in available if passive not in implant_passives)
    projected_owned = [
        replace(state, passives=frozenset(state.passives & breeding_available))
        for state in owned
    ]
    originals = {
        owned_state_identity(projected): original
        for original, projected in zip(owned, projected_owned)
    }
    states = search_states(
        projected_owned,
        breeding_available,
        frozenset(),
        strict=False,
        max_steps=3,
        per_species=64,
        global_limit=900,
    )
    routes = states + final_parent_routes(
        states,
        target_key,
        breeding_available,
        frozenset(),
        limit=500,
    )
    candidates = []
    for state in gender_filtered(routes, gender_preference):
        if state.species_key != target_key:
            continue
        forced = []
        priority_rank = 0
        available_on_candidate = set(state.passives) | implant_passives
        for group in priority_groups:
            selected_priority = next((passive for passive in group if passive in available_on_candidate), None)
            if selected_priority:
                forced.append(selected_priority)
                priority_rank += group.index(selected_priority)
            else:
                priority_rank += len(group)
        has_forced_insomnia = force_insomnia and "Insomnia" in available_on_candidate
        if force_insomnia and not has_forced_insomnia:
            priority_rank += 1
        speed_slots = 3 if has_forced_insomnia else 4
        selected = forced + [
            passive
            for passive in work_speed_passive_order(available_on_candidate, selection_scores)
            if passive not in forced and passive != "Insomnia"
        ][:max(0, speed_slots - len(forced))]
        if has_forced_insomnia and "Insomnia" not in selected:
            selected.append("Insomnia")
        if not selected:
            continue
        candidates.append((
            priority_rank,
            -sum(scores[passive] for passive in selected),
            -len(selected),
            len(state.passives - set(selected)),
            state.breed_count,
            state.steps,
            state.label,
            selected,
            state,
        ))
    if not candidates:
        return {"ideal": ideal, "selected": [], "route": None, "score": 0}

    best = min(candidates, key=lambda item: item[:-2])
    selected = best[-2]
    desired = frozenset(selected)
    return {
        "ideal": ideal,
        "selected": selected,
        "route": restore_profile_tree(best[-1], originals, desired),
        "score": sum(scores[passive] for passive in selected),
        "scores": scores,
    }


def profile_passives_payload(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"ok": False, "error": f"Unknown target species: {target_name}"}
    profile = payload.get("breedingProfile") or "work_speed"
    if profile not in {"work_speed", "ranch_drops_focus"}:
        return {"ok": False, "error": f"Profile is not automatic: {profile}"}
    priority_passive_groups = [["Ranch Master"], ["Farmhand"]] if profile == "ranch_drops_focus" else []
    result = best_work_speed_profile(
        owned_states_for_owner(owner),
        target_key,
        payload.get("genderPreference") or "any",
        include_insomnia=bool(payload.get("includeInsomnia")),
        priority_passive_groups=priority_passive_groups,
    )
    return {
        "ok": True,
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "breedingProfile": profile,
        "ideal": result.get("ideal", []),
        "selected": result.get("selected", []),
        "score": result.get("score", 0),
    }
