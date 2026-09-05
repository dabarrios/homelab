from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from pals.services import data, optimizer, work


class PalsRouteTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tester", password="test-password")

    def test_home_requires_login(self):
        response = self.client.get(reverse("pals:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_module_pages_load_for_authenticated_user(self):
        self.client.force_login(self.user)

        routes = [
            "pals:breeding",
            "pals:ivs",
            "pals:work",
            "pals:ranch",
            "pals:bases",
        ]

        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "window.PALS_API_BASE")
                self.assertContains(response, "pals/js/tool.js")
                self.assertNotContains(response, "module-rail")
                self.assertNotContains(response, "modeBreed")

    def test_home_loads_as_module_hub(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pals:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Palworld Analysis and Logistics Suite")
        self.assertNotContains(response, "window.PALS_API_BASE")

    def test_options_api_loads_for_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pals:api_options"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("species", response.json())
        self.assertIn("owners", response.json())

    def test_live_save_status_is_opt_in(self):
        self.client.force_login(self.user)

        with patch("pals.services.saves.LIVE_SAVE_DIR", None):
            response = self.client.get(reverse("pals:api_live_save_status"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIs(payload["configured"], False)
        self.assertEqual(payload["path"], "")


class WorkSpeedProfileTest(SimpleTestCase):
    def state(self, passives):
        return optimizer.State(
            species_key="target",
            species="Target Pal",
            passives=frozenset(passives),
            gender="Male",
            steps=0,
            breed_count=0,
            hp_iv=0,
            attack_iv=0,
            defense_iv=0,
            iv_total=0,
            iv_sources=1,
            label="Target Pal",
            location="Palbox",
            box=1,
            slot=1,
        )

    @patch("pals.services.optimizer.final_parent_routes", return_value=[])
    @patch("pals.services.optimizer.species_types_for_key", return_value=["Neutral"])
    def test_include_insomnia_uses_implant_slot_and_drops_lowest_speed(self, *_):
        result = optimizer.best_work_speed_profile(
            [
                self.state([
                    "Lucky",
                    "Remarkable Craftsmanship",
                    "Artisan",
                    "Work Slave",
                ])
            ],
            "target",
            "any",
            include_insomnia=True,
            implant_passives={"Insomnia"},
        )

        self.assertEqual(
            result["selected"],
            ["Remarkable Craftsmanship", "Artisan", "Lucky", "Insomnia"],
        )
        self.assertNotIn("Work Slave", result["selected"])

    @patch("pals.services.optimizer.final_parent_routes", return_value=[])
    @patch("pals.services.optimizer.species_types_for_key", return_value=["Neutral"])
    def test_insomnia_is_not_added_without_checkbox(self, *_):
        result = optimizer.best_work_speed_profile(
            [
                self.state([
                    "Lucky",
                    "Remarkable Craftsmanship",
                    "Artisan",
                    "Work Slave",
                ])
            ],
            "target",
            "any",
            include_insomnia=False,
            implant_passives={"Insomnia"},
        )

        self.assertEqual(
            result["selected"],
            ["Remarkable Craftsmanship", "Artisan", "Work Slave", "Lucky"],
        )


class IvAlphaOnlyTest(SimpleTestCase):
    def state(self, passives, *, is_alpha=False):
        return optimizer.State(
            species_key="jet",
            species="Jetragon",
            passives=frozenset(passives),
            gender="Male",
            steps=0,
            breed_count=0,
            hp_iv=100,
            attack_iv=100,
            defense_iv=100,
            iv_total=300,
            iv_sources=1,
            label="Jetragon Male L50 IV 100/100/100 Palbox",
            location="Palbox",
            box=1,
            slot=1,
            is_alpha=is_alpha,
        )

    def test_perfect_non_alpha_owned_match_returns_alpha_only_state(self):
        passives = ["Diamond Body", "Legend", "Divine Dragon", "Serenity"]
        store = SimpleNamespace(
            name_to_key={"jetragon": "jet"},
            passives=passives,
            pals={"jet": optimizer.BreedPal("jet", "Jetragon", 1, 1, True, False)},
        )

        with patch.object(optimizer, "STORE", store), patch(
            "pals.services.optimizer.owned_states_for_owner",
            return_value=[self.state(passives)],
        ):
            result = optimizer.build_iv_plan({
                "owner": "David",
                "target": "Jetragon",
                "passives": passives,
                "requireAlpha": True,
                "ivGoal": "perfect",
            })

        self.assertEqual(result["alphaOnly"]["state"], "missing_alpha")
        self.assertEqual(result["alphaOnly"]["missing"], ["Alpha"])
        self.assertEqual(result["alphaOnly"]["ownedMatch"]["isAlpha"], False)
        self.assertEqual(result["alphaOnly"]["recommendedCake"], "Special Cake")


class PassiveColorOverrideTest(SimpleTestCase):
    def test_data_store_includes_metadata_passives_not_owned_in_roster(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            breeding = root / "pals.json"
            roster = root / "pal_roster.csv"
            passive_inventory = root / "passive_inventory.csv"
            skill = root / "skill.json"
            breeding.write_text('{"pals": [], "uniqueCombos": [], "dataVersion": "test", "generatedAt": ""}', encoding="utf-8")
            roster.write_text("owner,passives\nDavid,Legend\n", encoding="utf-8")
            passive_inventory.write_text("passive_id,passive_name,count,pals\nLegend,Legend,1,\n", encoding="utf-8")
            skill.write_text(
                '{"en": {"WorldTree_MoveSpeed": {"name": "Dimensional Leap", "desc": "Movement Speed +50%"}}}',
                encoding="utf-8",
            )

            with patch.object(data, "BREEDING", breeding), patch.object(data, "ROSTER", roster), patch.object(data, "PASSIVE_INVENTORY", passive_inventory), patch.object(data, "SKILL_METADATA", skill), patch.object(data, "PASSIVE_COLOR_OVERRIDES_FILE", root / "overrides.json"):
                store = optimizer.DataStore()

        self.assertIn("Dimensional Leap", store.passives)
        self.assertIn("Legend", store.passives)
        self.assertEqual(store.passive_meta["Dimensional Leap"]["id"], "WorldTree_MoveSpeed")

    def test_element_boost_tiers_are_classified_from_passive_id(self):
        self.assertEqual(
            optimizer.passive_tone("Divine Dragon", "ElementBoost_Dragon_2_PAL", "30% increase in Dragon attack damage."),
            "gold",
        )
        self.assertEqual(
            optimizer.passive_tone("Blood of the Dragon", "ElementBoost_Dragon_1_PAL", "10% increase in Dragon attack damage."),
            "positive",
        )

    def test_passive_color_override_replaces_default_tone(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "passive_color_overrides.json"
            path.write_text('{"Serenity": "positive"}', encoding="utf-8")

            with patch.object(data, "PASSIVE_COLOR_OVERRIDES_FILE", path):
                meta = optimizer.build_passive_meta(["Serenity"])

        self.assertEqual(meta["Serenity"]["tone"], "positive")
        self.assertEqual(meta["Serenity"]["toneSource"], "override")


class WorkSuitabilityTest(SimpleTestCase):
    def test_owner_and_self_breeder_filters_preserve_verified_levels(self):
        store = SimpleNamespace(
            roster=[
                {"owner": "Alice", "species": "Worker"},
                {"owner": "Bob", "species": "Worker"},
            ],
            breeding_data={"pals": [
                {"key": "worker", "name": "Worker", "work": {"mining": 1}},
                {"key": "seed", "name": "Seed", "work": {"mining": 2}},
            ]},
            palpedia_work={"worker": {
                "baseWork": {"mining": 3},
                "fullyCondensedWork": {"mining": 7},
                "size": "M",
            }},
            parent_pairs_for_child=lambda key: [(key, key)] if key == "seed" else [("a", "b")],
        )
        with patch.object(work, "STORE", store), patch.object(work, "WORK_SUITABILITY_OVERRIDES", {}), patch.object(work, "icon_url_for_key", return_value=None):
            payload = work.work_suitability_payload("Alice", "mining", False)
            all_pals = work.work_suitability_payload("Alice", "mining", True)

        self.assertEqual(payload["total"], 1)
        card = payload["groups"][0]["cards"][0]
        self.assertEqual(card["ownedCount"], 1)
        self.assertEqual(card["selectedLevel"], 3)
        self.assertEqual(card["selectedFullyCondensedLevel"], 7)
        self.assertEqual(payload["verifiedCondensationCount"], 1)
        self.assertEqual(all_pals["total"], 2)
        seed = next(card for group in all_pals["groups"] for card in group["cards"] if card["key"] == "seed")
        self.assertTrue(seed["requiresOwnedSeed"])
        self.assertIsNone(seed["selectedFullyCondensedLevel"])
        self.assertEqual(seed["selectedProjectedFullyCondensedLevel"], 6)
