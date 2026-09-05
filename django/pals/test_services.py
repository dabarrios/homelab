"""Service boundaries and planner regression tests independent of local save data."""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from pals.services import bases, data, optimizer, saves, work


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

class IvBoundaryTests(SimpleTestCase):
    state = BreedingBoundaryTests.state

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
            if name != "optimizer":
                self.assertNotIn("optimizer", graph[name])
            if name not in {"optimizer", "legacy_http"}:
                self.assertNotIn("legacy_http", graph[name])
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

    def test_compatibility_exports_share_store_cache_and_function_identity(self):
        import importlib
        from pals.services import breeding, ivs, legacy_http
        for name in ["bases", "breeding", "breeding_state", "breeding_search", "breeding_profiles", "ivs", "work", "ranch", "saves", "legacy_http", "optimizer"]:
            module = importlib.import_module("pals.services." + name)
            self.assertIs(module.STORE, data.STORE)
        self.assertIs(optimizer.BASE_WORK_CACHE, bases.BASE_WORK_CACHE)
        self.assertIs(optimizer.build_plan, breeding.build_plan)
        self.assertIs(optimizer.profile_passives_payload, breeding.profile_passives_payload)
        self.assertIs(optimizer.build_iv_plan, ivs.build_iv_plan)
        self.assertIs(optimizer.build_base_planner, bases.build_base_planner)
        self.assertIs(optimizer.Handler, legacy_http.Handler)
        self.assertIs(optimizer.main, legacy_http.main)
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
    from pals.services import ivs, breeding, bases, optimizer, legacy_http
    assert optimizer.STORE is ivs.STORE is breeding.STORE is bases.STORE
    assert optimizer.BASE_WORK_CACHE is bases.BASE_WORK_CACHE
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
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        with patch.object(data.STORE, "reload") as reload, patch.object(bases, "BASE_WORK_CACHE", {"payload": {"old": True}, "mtime": 1}):
            response = views.reload_data(request)
            reload.assert_called_once_with()
            self.assertEqual(bases.BASE_WORK_CACHE, {"payload": None, "mtime": None})
        self.assertEqual(response.status_code, 200)

    def test_legacy_handler_delegates_without_opening_a_socket(self):
        from unittest.mock import Mock
        from pals.services import legacy_http
        handler = legacy_http.Handler.__new__(legacy_http.Handler)
        handler.path = "/api/base-work-sites"
        handler.send_json = Mock()
        with patch.object(legacy_http, "base_work_sites_payload", return_value={"ok": True, "bases": []}) as planner:
            handler.do_GET()
        planner.assert_called_once_with()
        handler.send_json.assert_called_once_with({"ok": True, "bases": []})
