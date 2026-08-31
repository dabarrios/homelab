from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from pals.services import optimizer


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

        with patch("pals.services.optimizer.LIVE_SAVE_DIR", None):
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
