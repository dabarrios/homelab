"""Service boundaries and planner regression tests independent of local save data."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pals.services import bases, data, saves, work


class BaseServiceTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        world = {
            "BaseCampSaveData": {"value": [{"value": {
                "WorkerDirector": {"value": {"RawData": {"value": {
                    "id": "base-a", "spawn_transform": {"translation": {"x": 0, "y": 0}},
                }}}},
                "WorkCollection": {"value": {"RawData": {"value": {"work_ids": ["mine", "mine", "missing"]}}}},
            }}]},
            "WorkSaveData": {"value": {"values": [{"RawData": {"value": {
                "id": "mine", "assign_define_data_id": "Mining", "owner_map_object_model_id": "ore",
            }}}]}},
        }
        (self.root / "Level.full.json").write_text(json.dumps({"properties": {"worldSaveData": {"value": world}}}))
        for name, value in [("WORK", self.root), ("BASE_LABELS_FILE", self.root / "labels.json"), ("BASE_WORK_CACHE", {"mtime": None, "payload": None})]:
            patcher = patch.object(bases, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_parsing_deduplicates_sites_and_refreshes_labels_on_cache_hit(self):
        first = bases.base_work_sites_payload()
        self.assertTrue(first["ok"])
        self.assertEqual(first["bases"][0]["siteCount"], 1)
        self.assertEqual(first["bases"][0]["unresolvedWorkIds"], 1)
        first["bases"][0]["sites"].clear()
        bases.save_base_labels({"base-a": "Ore Base"})
        with patch.object(bases, "load_level_world_data", side_effect=AssertionError("cache miss")):
            second = bases.base_work_sites_payload()
        self.assertEqual(second["bases"][0]["displayName"], "Ore Base")
        self.assertEqual(len(second["bases"][0]["sites"]), 1)
        self.assertEqual(bases.display_owned_location("Base 1 @ (0, 0)"), "Ore Base")
        saves.invalidate_refresh_dependents()
        self.assertEqual(bases.BASE_WORK_CACHE, {"mtime": None, "payload": None})

    def test_missing_world_returns_actionable_error(self):
        (self.root / "Level.full.json").unlink()
        result = bases.build_base_planner({})
        self.assertFalse(result["ok"])
        self.assertIn("Sync Save", result["error"])

    def test_owned_worker_adapter_supplies_base_label(self):
        bases.save_base_labels({"base-a": "Ore Base"})
        row = {"location": "Base 1 @ (0, 0)"}
        with patch.object(bases, "_owned_work_card", return_value={"ok": True}) as card:
            self.assertEqual(bases.work_card_for_owned_row(row), {"ok": True})
        card.assert_called_once_with(row, display_location="Ore Base")


class WorkerScoringTests(SimpleTestCase):
    def test_explicit_role_limits_and_disabled_roles_are_respected(self):
        targets = bases._planner_targets({"demand": {"mining": 3, "watering": 1}}, {
            "mining": {"min": 2, "max": 2}, "watering": {"min": 1, "max": 1},
            "transporting": {"enabled": False},
        }, 3)
        candidates = [{"plannerLevels": {"mining": 3, "watering": 2, "transporting": 1}}]
        slots = bases._allocate_role_slots(targets, candidates, 3)
        self.assertEqual(slots.count("mining"), 2)
        self.assertEqual(slots.count("watering"), 1)
        self.assertNotIn("transporting", slots)

    def test_owned_selection_excludes_used_instances_but_ideal_can_repeat(self):
        card = {"name": "Worker", "plannerInstanceId": "owned-a", "plannerLevels": {"mining": 3}}
        used = {"instance:owned-a": 1}
        self.assertIsNone(bases._best_for_role([card], "mining", used, {"mining"}, True))
        self.assertIs(bases._best_for_role([card], "mining", used, {"mining"}, False), card)

    def test_work_speed_scores_preserve_unicode_passive_names(self):
        from pals.services.breeding_profiles import work_speed_profile_scores
        self.assertEqual(work_speed_profile_scores()["Demon\u2019s Hand"], 90)

    def test_owned_card_retains_verified_levels_and_passive_scores(self):
        pal = {"key": "worker", "name": "Worker", "types": ["Neutral"], "work": {"mining": 2}}
        store = SimpleNamespace(name_to_key={"worker": "worker"}, breeding_data={"pals": [pal]}, palpedia_work={"worker": {
            "baseWork": {"mining": 2}, "fullyCondensedWork": {"mining": 6}, "size": "M",
        }})
        row = {"species": "Worker", "passives": "Artisan", "condensation_stars": "4", "location": "Palbox"}
        with patch.object(work, "STORE", store), patch.object(work, "WORK_SUITABILITY_OVERRIDES", {}), patch.object(work, "icon_url_for_key", return_value=None):
            card = work.work_card_for_owned_row(row, display_location="Ore Base")
        self.assertEqual(card["plannerLocation"], "Ore Base")
        self.assertEqual(card["selectedLevel"], 6)
        self.assertEqual(card["plannerPassiveSpeedScore"], 50)


class BreedingBoundaryTests(SimpleTestCase):
    def test_missing_sources_checks_all_ancestors_and_excludes_unrelated_donors(self):
        from dataclasses import replace
        from pals.services import breeding_search as search
        pairs = {"target": [("target", "bridge")], "bridge": [("seed", "bridge")], "seed": [("seed", "seed")]}
        store = SimpleNamespace(
            pals={key: SimpleNamespace(name=key) for key in ["target", "bridge", "seed", "outside"]},
            parent_pairs_for_child=lambda key: pairs.get(key, []),
        )
        owned = [
            self.state("Male", ["Burly Body"]),
            replace(self.state("Male", ["Reload Master"]), species_key="seed"),
            replace(self.state("Female", ["Idiosyncratic"]), species_key="outside"),
        ]
        target = frozenset(["Idiosyncratic", "Reload Master"])
        with patch.object(search, "STORE", store):
            result = search.missing_passive_sources(owned, "target", target)
            self.assertEqual(result["missingPassives"], ["Idiosyncratic"])
            self.assertEqual(result["sourceSpecies"], ["bridge", "seed", "target"])
            owned.append(replace(owned[-1], species_key="seed"))
            self.assertEqual(search.missing_passive_sources(owned, "target", target)["missingPassives"], [])

    def test_final_routes_cache_donors_once_per_species(self):
        from pals.services import breeding_search as search
        parents = [self.state("Male", ["Artisan"]), self.state("Female", ["Serious"])]
        store = SimpleNamespace(
            pals={"target": SimpleNamespace(name="Target")},
            parent_pairs_for_child=lambda key: [("target", "target"), ("target", "target")],
        )
        with patch.object(search, "STORE", store), patch.object(search, "top_donors_for_species", wraps=search.top_donors_for_species) as donors:
            routes = search.final_parent_routes(parents, "target", frozenset(["Artisan", "Serious"]), frozenset())
        self.assertEqual(donors.call_count, 1)
        self.assertEqual(len(routes), 2)
        self.assertEqual(set(routes[0].parents), set(parents))

    def state(self, gender, passives, *, label="Owned", base_workers=0, hp=100):
        from pals.services.breeding_state import State
        return State(
            species_key="target", species="Target", passives=frozenset(passives),
            gender=gender, steps=0, breed_count=0, hp_iv=hp, attack_iv=80,
            defense_iv=60, iv_total=hp + 140, iv_sources=1, label=label,
            location="Palbox", box=1, slot=1, base_workers_used=base_workers,
        )

    def test_search_preserves_inheritance_and_filters_junk(self):
        from pals.services import breeding_search as search
        parents = [self.state("Male", ["Artisan"]), self.state("Female", ["Serious"]), self.state("Female", ["Clumsy"], label="Junk")]
        store = SimpleNamespace(child_for=lambda a, b: "target", pals={"target": SimpleNamespace(name="Target")})
        target = frozenset(["Artisan", "Serious"])
        with patch.object(search, "STORE", store):
            strict = search.search_states(parents, target, frozenset(), strict=True, max_steps=1, per_species=30, global_limit=30)
            practical = search.search_states(parents, target, frozenset(), strict=False, max_steps=1, per_species=30, global_limit=30)
        child = next(s for s in strict if s.parents)
        self.assertEqual(child.passives, target)
        self.assertEqual(child.gender, "Either")
        self.assertEqual((child.breed_count, child.steps, child.iv_sources), (1, 1, 2))
        self.assertEqual(child.avg_hp_iv, 100)
        self.assertTrue(all("Clumsy" not in s.passives for s in strict))
        self.assertTrue(any(s.parents and "Clumsy" in s.passives for s in practical))

    def test_storage_substitution_recalculates_tree_without_changing_parent(self):
        from dataclasses import replace
        from pals.services.breeding_state import substitute_storage_leaves
        base = self.state("Male", ["Artisan"], label="Base", base_workers=1, hp=20)
        storage = self.state("Male", ["Artisan"], label="Storage", hp=100)
        other = self.state("Female", ["Serious"])
        child = replace(base, gender="Either", parents=(base, other), steps=1, breed_count=1)
        result = substitute_storage_leaves(child, [storage], frozenset(["Artisan", "Serious"]), frozenset())
        self.assertIs(result.parents[0], storage)
        self.assertEqual(result.base_workers_used, 0)
        self.assertEqual(result.avg_hp_iv, 100)
        self.assertEqual(result.passives, frozenset(["Artisan", "Serious"]))
        self.assertIs(child.parents[0], base)
        self.assertEqual(base.hp_iv, 20)

    def test_serialization_resolves_parent_genders_and_deduplicates_routes(self):
        from dataclasses import replace
        from pals.services import breeding_serialization as serialization
        a = self.state("Male", ["Artisan"])
        b = self.state("Either", ["Serious"])
        child = replace(a, gender="Either", passives=a.passives | b.passives, parents=(a, b), steps=1, breed_count=1)
        with patch.object(serialization, "icon_url_for_key", return_value=None), patch.object(serialization, "species_types_for_key", return_value=["Neutral"]):
            result = serialization.unique_serialized([child, child], child.passives, frozenset(), 6, intended_gender="Female")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["displayGender"], "Female")
        self.assertEqual({p["displayGender"] for p in result[0]["parents"]}, {"Male", "Female"})
        self.assertEqual(result[0]["missing"], [])
        self.assertEqual(result[0]["suggestedCakes"], 1)

class BreedAnywayTests(SimpleTestCase):
    state = BreedingBoundaryTests.state

    def setUp(self):
        from pals.services import breeding, breeding_search, breeding_serialization
        self.breeding = breeding
        self.passives = ["Lavish Hospitality", "Service-Minded"]
        self.parents = [
            self.state("Male", self.passives, label="Owned male"),
            self.state("Female", [], label="Owned female"),
        ]
        store = SimpleNamespace(
            name_to_key={"target": "target"},
            pals={"target": SimpleNamespace(name="Target")},
            parent_pairs_for_child=lambda key: [("target", "target")],
            child_for=lambda a, b: "target",
        )
        for module, name, value in [
            (breeding, "STORE", store), (breeding_search, "STORE", store),
            (breeding, "owned_states_for_owner", lambda owner: self.parents),
            (breeding_serialization, "icon_url_for_key", lambda key: None),
            (breeding_serialization, "species_types_for_key", lambda key: []),
        ]:
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def plan(self, **options):
        return self.breeding.build_plan({"target": "Target", "passives": self.passives, **options})

    def test_default_still_recommends_owned_match(self):
        result = self.plan()
        self.assertFalse(result["breedAnyway"])
        self.assertFalse(result["results"][0]["parents"])

    def test_breed_anyway_returns_owned_pair_instead_of_owned_match(self):
        result = self.plan(breedAnyway=True)
        self.assertTrue(result["achievable"])
        self.assertEqual(result["alreadyOwned"]["count"], 1)
        pair = result["results"][0]["parents"]
        self.assertEqual(len(pair), 2)
        self.assertTrue(all(not parent["parents"] for parent in pair))
        self.assertEqual({parent["gender"] for parent in pair}, {"Male", "Female"})
        self.assertTrue(all(route["parents"] for group in result["groups"] for route in group["results"]))

    def test_single_owned_match_is_not_a_breeding_pair(self):
        self.parents = self.parents[:1]
        result = self.plan(breedAnyway=True)
        self.assertFalse(result["achievable"])
        self.assertEqual(result["results"], [])
        self.assertTrue(all(not group["results"] for group in result["groups"]))

    def test_same_gender_pals_are_not_a_breeding_pair(self):
        from dataclasses import replace
        self.parents[1] = replace(self.parents[1], gender="Male")
        result = self.plan(breedAnyway=True)
        self.assertFalse(result["achievable"])
        self.assertEqual(result["noRoute"]["reason"], "search_exhausted")
        self.assertEqual(result["noRoute"]["missingPassives"], [])

    def test_missing_donor_returns_partial_breeding_plan_without_claiming_complete_goal(self):
        from dataclasses import replace
        self.parents[0] = replace(self.parents[0], passives=frozenset(self.passives[:1]))
        result = self.plan()
        self.assertFalse(result["achievable"])
        self.assertEqual(result["results"], [])
        diagnosis = result["noRoute"]
        self.assertEqual(diagnosis["reason"], "missing_sources")
        self.assertEqual(diagnosis["missingPassives"], self.passives[1:])
        self.assertEqual(diagnosis["partialPassives"], self.passives[:1])
        partial = diagnosis["partialResults"][0]
        self.assertEqual(len(partial["parents"]), 2)
        self.assertEqual(partial["desired"], self.passives[:1])

    def test_continue_progress_and_gender_preference_still_require_parents(self):
        result = self.plan(breedAnyway=True, routePreference="continue_progress", genderPreference="Female")
        self.assertTrue(result["results"][0]["parents"])
        self.assertEqual(result["results"][0]["displayGender"], "Female")

    def test_false_string_does_not_enable_breed_anyway(self):
        self.assertFalse(self.plan(breedAnyway="false")["breedAnyway"])


class IvBoundaryTests(SimpleTestCase):
    state = BreedingBoundaryTests.state

    def test_perfect_alpha_is_complete_even_when_non_alpha_is_owned(self):
        from dataclasses import replace
        from pals.services import ivs
        normal = replace(self.state("Male", ["Artisan"]), attack_iv=100, defense_iv=100, iv_total=300)
        alpha = replace(normal, is_alpha=True, label="Alpha")
        store = SimpleNamespace(name_to_key={"target": "target"}, pals={"target": SimpleNamespace(name="Target")})
        with patch.object(ivs, "STORE", store), patch.object(ivs, "owned_states_for_owner", return_value=[normal, alpha]), patch.object(ivs, "icon_url_for_key", return_value=None):
            result = ivs.build_iv_plan({"target": "Target", "passives": ["Artisan"], "requireAlpha": True})
        self.assertEqual(result["alphaOnly"]["state"], "complete")
        self.assertTrue(result["alphaOnly"]["ownedMatch"]["isAlpha"])
        self.assertEqual(result["alphaOnly"]["missing"], [])

    def test_implants_relax_natural_pool_without_changing_parent_passives(self):
        from pals.services import ivs
        parents = [self.state("Male", ["Artisan"], label="A"), self.state("Female", ["Artisan"], label="B")]
        store = SimpleNamespace(name_to_key={"target": "target"}, pals={"target": SimpleNamespace(name="Target")})
        payload = {"target": "Target", "owner": "Alice", "passives": ["Artisan", "Serious"]}
        with patch.object(ivs, "STORE", store), patch.object(ivs, "owned_states_for_owner", return_value=parents), patch.object(ivs, "icon_url_for_key", return_value=None):
            natural = ivs.build_iv_plan(payload)
            implanted = ivs.build_iv_plan({**payload, "implantPassives": ["Serious"]})
        self.assertEqual(natural["matchingCount"], 0)
        self.assertEqual(implanted["matchingCount"], 2)
        self.assertEqual(implanted["naturalPassives"], ["Artisan"])
        self.assertEqual(implanted["pairs"][0]["missing"], [])
        self.assertEqual(parents[0].passives, frozenset(["Artisan"]))

    def test_unknown_species_and_missing_passives_are_rejected(self):
        from pals.services import ivs
        with patch.object(ivs, "STORE", SimpleNamespace(name_to_key={"target": "target"})):
            self.assertIn("Unknown target", ivs.build_iv_plan({"target": "Missing"})["error"])
            self.assertIn("Choose the passives", ivs.build_iv_plan({"target": "Target"})["error"])



class ServiceArchitectureTests(SimpleTestCase):
    def test_service_import_graph_is_acyclic_and_domains_do_not_import_facade(self):
        import ast
        root = Path(data.__file__).parent
        modules = {p.stem: ast.parse(p.read_text()) for p in root.glob("*.py")}
        graph = {}
        for name, tree in modules.items():
            graph[name] = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module in modules}
            dependencies = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level == 1}
            self.assertNotIn("optimizer", dependencies)
            self.assertNotIn("legacy_http", dependencies)
        visited = set()
        def visit(name, active):
            self.assertNotIn(name, active, f"Circular imports: {active} -> {name}")
            if name in visited:
                return
            for dependency in graph[name]:
                visit(dependency, [*active, name])
            visited.add(name)
        for name in graph:
            visit(name, [])

    def test_services_share_store_and_register_one_cache_hook(self):
        import importlib
        for name in ["bases", "breeding", "breeding_state", "breeding_search", "breeding_profiles", "ivs", "work", "ranch", "saves"]:
            module = importlib.import_module("pals.services." + name)
            self.assertIs(module.STORE, data.STORE)
        self.assertEqual(saves._refresh_hooks.count(bases.clear_base_work_cache), 1)

    def test_fresh_domain_imports_do_not_start_server_or_sync(self):
        import subprocess
        import sys
        code = '''
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from unittest.mock import patch
with patch("http.server.ThreadingHTTPServer", side_effect=AssertionError("server started")), patch("threading.Thread.start", side_effect=AssertionError("thread started")):
    from pals.services import ivs, breeding, bases, work, saves
    assert work.STORE is ivs.STORE is breeding.STORE is bases.STORE
    assert saves._refresh_hooks.count(bases.clear_base_work_cache) == 1
'''
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(data.__file__).parents[2], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


class ServiceEndpointTests(SimpleTestCase):
    def test_planner_endpoints_forward_to_public_domain_services(self):
        from django.test import RequestFactory
        from pals import views
        from pals.services import breeding, ivs
        payload = {"owner": "Alice", "target": "Target", "passives": ["Artisan"]}
        for view, module, function in [(views.optimize, breeding, "build_plan"), (views.profile_passives, breeding, "profile_passives_payload"), (views.improve_ivs, ivs, "build_iv_plan"), (views.base_planner, bases, "build_base_planner")]:
            with self.subTest(function=function):
                request = RequestFactory().post("/", data=json.dumps(payload), content_type="application/json")
                request.user = SimpleNamespace(is_authenticated=True)
                with patch.object(module, function, return_value={"ok": True, "result": function}) as planner:
                    response = view(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(json.loads(response.content), {"ok": True, "result": function})
                planner.assert_called_once_with(payload)

    def test_reload_invalidates_the_domain_cache(self):
        from django.test import RequestFactory
        from pals import views
        request = RequestFactory().post("/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch.object(data.STORE, "reload") as reload, patch.object(bases, "BASE_WORK_CACHE", {"payload": {"old": True}, "mtime": 1}):
            response = views.reload_data(request)
            reload.assert_called_once_with()
            self.assertEqual(bases.BASE_WORK_CACHE, {"payload": None, "mtime": None})
        self.assertEqual(response.status_code, 200)
