"""Existing breeding progress scoring and explanations."""

from __future__ import annotations

from .breeding_state import State, iv_sort_bits, junk_count, walk_tree


def progress_leaf_score(s: State, target: frozenset[str], allowed: frozenset[str]) -> int:
    if s.parents or junk_count(s, target, allowed):
        return 0
    desired = len(s.passives & target)
    if target and target <= s.passives:
        return 120
    if desired >= max(1, len(target) - 1):
        return 70
    if desired >= 2:
        return 25
    return 0


def progress_species(owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> set[str]:
    return {s.species_key for s in owned if progress_leaf_score(s, target, allowed) >= 70}


def progress_score(s: State, target: frozenset[str], allowed: frozenset[str], progressed_species: set[str]) -> int:
    score = 0
    if s.parents:
        for parent in s.parents:
            if parent.species_key in progressed_species:
                score += 500
    seen_leaves: set[tuple] = set()
    seen_species: set[str] = set()
    for node in walk_tree(s):
        if node.species_key in progressed_species and node.species_key not in seen_species:
            score += 30
            seen_species.add(node.species_key)
        if not node.parents:
            leaf_key = (node.species_key, node.gender, node.location, tuple(sorted(node.passives)))
            if leaf_key not in seen_leaves:
                score += progress_leaf_score(node, target, allowed)
                seen_leaves.add(leaf_key)
    return score


def progress_sort_key(s: State, target: frozenset[str], allowed: frozenset[str], progressed_species: set[str], iv_preference: str = "none"):
    desired = len(s.passives & target)
    missing = len(target - s.passives)
    junk = junk_count(s, target, allowed)
    return (missing, junk, s.breed_count, s.steps, -progress_score(s, target, allowed, progressed_species), -desired, *iv_sort_bits(s, iv_preference), s.label)


def progress_notes(s: State, target: frozenset[str], allowed: frozenset[str]) -> list[str]:
    notes = []
    progressed = []
    if s.parents:
        for parent in s.parents:
            if target <= parent.passives and not junk_count(parent, target, allowed):
                progressed.append(parent.species)
        for species in sorted(set(progressed)):
            notes.append(f"Continues clean {species} progress as a final parent line.")
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for node in walk_tree(s):
        if node.parents or junk_count(node, target, allowed):
            continue
        desired = sorted(node.passives & target)
        if len(desired) < max(2, len(target) - 1):
            continue
        key = (node.species, tuple(desired))
        if key in seen:
            continue
        seen.add(key)
        if target <= node.passives:
            notes.append(f"Reuses owned clean {node.species} with all desired passives ({node.gender}).")
        else:
            missing = sorted(target - node.passives)
            notes.append(f"Reuses owned clean {node.species} with {len(desired)}/{len(target)} desired; missing {', '.join(missing)}.")
        if len(notes) >= 3:
            break
    return notes
