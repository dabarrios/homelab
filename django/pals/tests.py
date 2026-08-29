from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
            "pals:home",
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

    def test_options_api_loads_for_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pals:api_options"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("species", response.json())
        self.assertIn("owners", response.json())

    def test_live_save_status_is_opt_in(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pals:api_live_save_status"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIs(payload["configured"], False)
        self.assertEqual(payload["path"], "")
