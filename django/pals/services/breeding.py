"""Public breeding planner entry point."""

from __future__ import annotations

from .breeding_profiles import best_work_speed_profile, profile_passives_payload
from .breeding_progress import progress_species
from .breeding_search import final_parent_routes, search_states
from .breeding_serialization import build_group, unique_serialized
from .breeding_state import (
    gender_filtered,
    owned_states_for_owner,
    ready_to_finish_states,
    target_complete,
)
from .data import STORE, as_bool, canonical_passives
from .ivs import available_implant_passives
from .work import WORK_SPEED_PASSIVE_SCORE


def build_plan(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"error": f"Unknown target species: {target_name}"}
    final_target = canonical_passives(payload.get("passives", []))
    include_implants = bool(payload.get("includeImplants"))
    inventory_implants = available_implant_passives() if include_implants else set()
    implant_passives = (canonical_passives(payload.get("implantPassives", [])) | inventory_implants) & final_target
    target = frozenset(final_target - implant_passives)
    allowed = canonical_passives(payload.get("allowedExtras", [])) | implant_passives
    gender_preference = payload.get("genderPreference") or "any"
    iv_preference = "none"
    route_preference = payload.get("routePreference") or "best_overall"
    breeding_profile = payload.get("breedingProfile") or "manual"
    breed_anyway = as_bool(payload.get("breedAnyway"))
    owned = owned_states_for_owner(owner)
    work_speed_profile = None
    profile_route = None
    if breeding_profile in {"work_speed", "ranch_drops_focus"}:
        priority_passive_groups = [["Ranch Master"], ["Farmhand"]] if breeding_profile == "ranch_drops_focus" else []
        work_speed_profile = best_work_speed_profile(
            owned,
            target_key,
            gender_preference,
            include_insomnia=bool(payload.get("includeInsomnia")),
            priority_passive_groups=priority_passive_groups,
            implant_passives=inventory_implants,
        )
        if work_speed_profile["selected"]:
            final_target = frozenset(work_speed_profile["selected"])
            implant_passives = (implant_passives | inventory_implants) & final_target
            target = frozenset(final_target - implant_passives)
            allowed = allowed | implant_passives
            profile_route = work_speed_profile["route"]
    progressed = progress_species(owned, target, allowed)

    clean_states = search_states(owned, target, allowed, strict=True, max_steps=4, per_species=8, global_limit=450, iv_preference=iv_preference)
    practical_states = search_states(owned, target, allowed, strict=False, max_steps=3, per_species=10, global_limit=550, iv_preference=iv_preference)
    fastest_states = search_states(owned, target, allowed, strict=False, max_steps=2, per_species=10, global_limit=450, iv_preference=iv_preference)
    clean_routes = clean_states + final_parent_routes(clean_states, target_key, target, allowed, iv_preference=iv_preference)
    practical_routes = practical_states + final_parent_routes(practical_states, target_key, target, allowed, iv_preference=iv_preference)
    fastest_routes = fastest_states + final_parent_routes(fastest_states, target_key, target, allowed, iv_preference=iv_preference)
    if profile_route:
        clean_routes.append(profile_route)
        practical_routes.append(profile_route)
        fastest_routes.append(profile_route)
    if breed_anyway:
        # Search compaction may discard repeat offspring in favor of an owned match.
        direct_routes = final_parent_routes(owned, target_key, target, allowed, iv_preference=iv_preference)
        clean_routes = [s for s in clean_routes + direct_routes if s.parents and not (s.passives - target - allowed)]
        practical_routes = [s for s in practical_routes + direct_routes if s.parents]
        fastest_routes = [s for s in fastest_routes + direct_routes if s.parents]
    owned_target_states = [s for s in owned if s.species_key == target_key]
    owned_matching_target_states = [s for s in owned_target_states if target_complete(s, target)]
    owned_matching_target_for_gender = gender_filtered(owned_matching_target_states, gender_preference)
    ready_finish_states = ready_to_finish_states(
        owned_target_states,
        final_target,
        frozenset(implant_passives),
        gender_preference,
    )

    clean_group = build_group(
        "cleanest",
        "Cleanest Route",
        "No junk passives in the inherited pool. May take more setup breeds.",
        clean_routes,
        target_key,
        target,
        allowed,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    fastest_group = build_group(
        "fastest",
        "Fastest Route",
        "Fewest total eggs with all desired passives present, even if the passive pool is messy.",
        fastest_routes,
        target_key,
        target,
        allowed,
        fastest=True,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    practical_group = build_group(
        "least_junk",
        "Least-Junk Practical Route",
        "Middle ground: all desired passives, then fewer junk passives, then fewer setup breeds.",
        practical_routes,
        target_key,
        target,
        allowed,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    existing_group = build_group(
        "existing_target",
        "Best Existing Target",
        "Owned target-species Pals that are already close and may be good consolidation parents.",
        owned_target_states,
        target_key,
        target,
        allowed,
        complete_only=False,
        iv_preference=iv_preference,
    )

    all_route_states = gender_filtered(practical_routes + clean_routes + fastest_routes, gender_preference)
    progress_candidates = [s for s in all_route_states if s.species_key == target_key and target_complete(s, target)]
    progress_group = {
        "slug": "continue_progress",
        "title": "Continue Progress",
        "description": "Favors clean owned 3/4 or 4/4 intermediate work when you rerun the same target/passives after syncing.",
        "results": unique_serialized(progress_candidates, target, allowed, 6, iv_preference=iv_preference, progress_species_set=progressed, intended_gender=gender_preference, replacement_pool=owned),
    }

    recommended_pool = owned_matching_target_for_gender or owned_matching_target_states or []
    if breed_anyway:
        recommended_pool = []
    recommended_states = [s for s in recommended_pool + all_route_states if s.species_key == target_key and target_complete(s, target)]
    if route_preference == "continue_progress" and progress_group["results"]:
        recommended = progress_group["results"][:3]
        recommended_description = "Best continuation of your synced progress for the same target/passives."
    else:
        recommended = unique_serialized(recommended_states, target, allowed, 3, iv_preference=iv_preference, intended_gender=gender_preference, replacement_pool=owned)
        recommended_description = "Best practical option from the searches below."
    achievable = bool(recommended)
    profile_ideal = work_speed_profile["ideal"] if work_speed_profile else []
    profile_selected = work_speed_profile["selected"] if work_speed_profile else []
    profile_score = work_speed_profile["score"] if work_speed_profile else 0
    profile_disclaimer = ""
    if work_speed_profile and profile_selected and profile_selected != profile_ideal:
        available = {passive for state in owned for passive in state.passives}
        reasons = []
        for passive in profile_ideal:
            if passive in profile_selected:
                continue
            if passive not in available and passive not in inventory_implants:
                reasons.append(f"{passive} is not owned or available as an implant")
            else:
                reasons.append(f"{passive} could not be included in a stronger reachable combination")
        profile_scores = work_speed_profile.get("scores", WORK_SPEED_PASSIVE_SCORE)
        ideal_score = sum(profile_scores[passive] for passive in profile_ideal)
        profile_disclaimer = (
            f"Using the fastest reachable combination (+{profile_score}% work speed). "
            f"The absolute +{ideal_score}% combination was not selected because "
            + "; ".join(reasons)
            + "."
        )
    groups = [
        {
            "slug": "recommended",
            "title": "Recommended",
            "description": recommended_description,
            "results": recommended,
        },
    ]
    if route_preference == "continue_progress":
        groups.append(progress_group)
    groups.extend([
        clean_group,
        fastest_group,
        practical_group,
    ])
    if not breed_anyway:
        groups.append(existing_group)
    return {
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "requestedPassives": sorted(target),
        "finalPassives": sorted(final_target),
        "implantPassives": sorted(implant_passives),
        "allowedExtras": sorted(allowed),
        "ownedCount": len(owned),
        "genderPreference": gender_preference,
        "ivPreference": iv_preference,
        "routePreference": route_preference,
        "breedingProfile": breeding_profile,
        "breedAnyway": breed_anyway,
        "achievable": achievable,
        "profileIdealPassives": profile_ideal,
        "profileSelectedPassives": profile_selected,
        "profileWorkSpeedBonus": profile_score,
        "profileDisclaimer": profile_disclaimer,
        "progressedSpecies": sorted(STORE.pals[key].name for key in progressed if key in STORE.pals),
        "alreadyOwned": {
            "count": len(owned_matching_target_states),
            "matchingGenderCount": len(owned_matching_target_for_gender),
            "results": unique_serialized(owned_matching_target_for_gender or owned_matching_target_states, target, allowed, 6, iv_preference=iv_preference, intended_gender=gender_preference),
        },
        "readyToFinish": {
            "count": len(ready_finish_states),
            "results": unique_serialized(ready_finish_states, final_target, implant_passives, 6, iv_preference=iv_preference, intended_gender=gender_preference),
        },
        "groups": groups,
        "results": recommended,
    }


def module_status() -> dict[str, str]:
    return {"state": "ready", "message": "Breeding planning and automatic profiles are available."}
