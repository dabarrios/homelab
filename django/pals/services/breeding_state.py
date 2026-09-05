"""Owned breeding state, ranking, and tree transformations."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .bases import display_owned_location
from .data import (
    DataStore,
    STORE,
    as_bool,
    as_int,
    base_slot,
    normalize_species,
    palbox_position,
    split_passives,
)


@dataclass(frozen=True)
class State:
    species_key: str
    species: str
    passives: frozenset[str]
    gender: str
    steps: int
    breed_count: int
    hp_iv: int
    attack_iv: int
    defense_iv: int
    iv_total: int
    iv_sources: int
    label: str
    location: str
    box: int | None
    slot: int | None
    base_slot: int | None = None
    base_workers_used: int = 0
    instance_id: str = ""
    is_alpha: bool = False
    parents: tuple["State", "State"] | None = None

    @property
    def id(self) -> str:
        return f"{self.species_key}|{','.join(sorted(self.passives))}|{self.gender}|{self.steps}|{self.breed_count}|{self.label}"

    @property
    def avg_iv(self) -> float:
        return self.iv_total / max(1, self.iv_sources)

    @property
    def avg_hp_iv(self) -> float:
        return self.hp_iv / max(1, self.iv_sources)

    @property
    def avg_attack_iv(self) -> float:
        return self.attack_iv / max(1, self.iv_sources)

    @property
    def avg_defense_iv(self) -> float:
        return self.defense_iv / max(1, self.iv_sources)


def row_to_state(row: dict[str, str], store: DataStore) -> State | None:
    species = normalize_species(row.get("species", ""))
    key = store.name_to_key.get(species.lower())
    if not key:
        return None
    raw_location = row.get("location", "") or ""
    location = display_owned_location(raw_location)
    pos = palbox_position(raw_location)
    base_slot_number = base_slot(raw_location)
    hp_iv = as_int(row.get("hp_iv"))
    attack_iv = as_int(row.get("attack_iv"))
    defense_iv = as_int(row.get("defense_iv"))
    iv_total = hp_iv + attack_iv + defense_iv
    nick = row.get("nickname") or species
    label = f"{species} {row.get('gender') or '?'} L{row.get('level') or 0} [{nick}] IV {row.get('hp_iv')}/{row.get('attack_iv')}/{row.get('defense_iv')}"
    if pos["box"]:
        label += f" Box {pos['box']} Slot {pos['slot']}"
    elif base_slot_number is not None:
        label += f" {location} Slot {base_slot_number}"
    else:
        label += f" {location}"
    return State(
        species_key=key,
        species=species,
        passives=split_passives(row.get("passives")),
        gender=row.get("gender") or "Unknown",
        steps=0,
        breed_count=0,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=iv_total,
        iv_sources=1,
        label=label,
        location=location,
        box=pos["box"],
        slot=pos["slot"],
        base_slot=base_slot_number,
        base_workers_used=owned_location_base_penalty(raw_location),
        instance_id=row.get("instance_id") or "",
        is_alpha=as_bool(row.get("is_boss")),
    )


def compatible(a: State, b: State) -> bool:
    fixed = {a.gender, b.gender}
    if "Either" in fixed or "Unknown" in fixed:
        return True
    return fixed == {"Male", "Female"}


def iv_sort_bits(s: State, iv_preference: str) -> tuple:
    if iv_preference == "highest_iv":
        return (-s.avg_iv, -s.avg_attack_iv)
    if iv_preference == "highest_attack":
        return (-s.avg_attack_iv, -s.avg_iv)
    if iv_preference == "balanced_iv":
        weakest = min(s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv)
        return (-weakest, -s.avg_iv, -s.avg_attack_iv, -s.avg_hp_iv, -s.avg_defense_iv)
    if iv_preference == "survival_iv":
        return (-(s.avg_hp_iv + s.avg_defense_iv) / 2, -s.avg_hp_iv, -s.avg_defense_iv, -s.avg_attack_iv)
    return ()


def owned_location_base_penalty(location: str) -> int:
    lower = (location or "").lower()
    if lower.startswith("base "):
        return 1
    return 0


def state_score(s: State, target: frozenset[str], allowed: frozenset[str], iv_preference: str = "none"):
    desired = len(s.passives & target)
    junk = len(s.passives - target - allowed)
    missing = len(target - s.passives)
    return (-desired, junk, missing, s.breed_count, s.steps, *iv_sort_bits(s, iv_preference), s.label)


def compact_states(states: list[State], target: frozenset[str], allowed: frozenset[str], per_species=30, iv_preference: str = "none") -> list[State]:
    grouped: dict[str, dict[tuple[frozenset[str], str], State]] = {}
    for s in states:
        by_pool = grouped.setdefault(s.species_key, {})
        key = (s.passives, s.gender)
        existing = by_pool.get(key)
        if existing is None or state_score(s, target, allowed, iv_preference) < state_score(existing, target, allowed, iv_preference):
            by_pool[key] = s
    kept = []
    for group in grouped.values():
        kept.extend(sorted(group.values(), key=lambda s: state_score(s, target, allowed, iv_preference))[:per_species])
    return kept


def target_complete(s: State, target: frozenset[str]) -> bool:
    return target <= s.passives


def junk_count(s: State, target: frozenset[str], allowed: frozenset[str]) -> int:
    return len(s.passives - target - allowed)


def result_sort_key(s: State, target: frozenset[str], allowed: frozenset[str], *, fastest: bool = False, iv_preference: str = "none", prefer_storage: bool = False):
    desired = len(s.passives & target)
    junk = junk_count(s, target, allowed)
    missing = len(target - s.passives)
    storage_bits = (s.base_workers_used,) if prefer_storage else ()
    if fastest:
        return (missing, s.breed_count, s.steps, junk, -desired, *iv_sort_bits(s, iv_preference), *storage_bits, s.label)
    return (missing, junk, s.breed_count, s.steps, -desired, *iv_sort_bits(s, iv_preference), *storage_bits, s.label)


def owned_states_for_owner(owner: str) -> list[State]:
    owned = [row_to_state(r, STORE) for r in STORE.roster if (r.get("owner") or "").lower() == owner]
    return [s for s in owned if s]


def gender_matches(s: State, preference: str) -> bool:
    return preference in {"", "any", "Any", None} or s.gender == preference or s.gender == "Either"


def gender_filtered(states: list[State], preference: str) -> list[State]:
    return [s for s in states if gender_matches(s, preference)]


def walk_tree(s: State):
    yield s
    if s.parents:
        yield from walk_tree(s.parents[0])
        yield from walk_tree(s.parents[1])


def tree_signature(s: State) -> tuple:
    if not s.parents:
        return ("owned", s.species_key, tuple(sorted(s.passives)), s.gender, s.location, s.box, s.slot)
    return (
        "bred",
        s.species_key,
        tuple(sorted(s.passives)),
        tuple(sorted((tree_signature(s.parents[0]), tree_signature(s.parents[1])), key=repr)),
    )


def ready_to_finish_states(
    owned_target_states: list[State],
    final_target: frozenset[str],
    implant_passives: frozenset[str],
    gender_preference: str,
) -> list[State]:
    if not final_target or not implant_passives:
        return []
    candidates = []
    for state in gender_filtered(owned_target_states, gender_preference):
        missing = final_target - state.passives
        if not missing:
            continue
        if missing <= implant_passives and final_target <= (state.passives | implant_passives):
            candidates.append(state)
    return candidates


def best_storage_substitute(s: State, owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> State | None:
    if s.parents or not s.base_workers_used:
        return None
    required = s.passives & target
    if not required:
        return None
    candidates = [
        candidate for candidate in owned
        if (
            not candidate.parents
            and not candidate.base_workers_used
            and candidate.species_key == s.species_key
            and candidate.gender == s.gender
            and required <= candidate.passives
        )
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: state_score(candidate, target, allowed))[0]


def substitute_storage_leaves(s: State, owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> State:
    if not s.parents:
        return best_storage_substitute(s, owned, target, allowed) or s
    parents = (
        substitute_storage_leaves(s.parents[0], owned, target, allowed),
        substitute_storage_leaves(s.parents[1], owned, target, allowed),
    )
    pool = frozenset(set(parents[0].passives) | set(parents[1].passives))
    hp_iv = parents[0].hp_iv + parents[1].hp_iv
    attack_iv = parents[0].attack_iv + parents[1].attack_iv
    defense_iv = parents[0].defense_iv + parents[1].defense_iv
    return replace(
        s,
        passives=pool,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=hp_iv + attack_iv + defense_iv,
        iv_sources=parents[0].iv_sources + parents[1].iv_sources,
        base_workers_used=parents[0].base_workers_used + parents[1].base_workers_used,
        parents=parents,
    )
