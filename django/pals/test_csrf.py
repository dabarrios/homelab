import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from pals.services import breeding, data, saves


class PalsCsrfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="csrf-tester")

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        page = self.client.get(reverse("pals:breeding"))
        self.assertEqual(page.status_code, 200)
        self.token = re.search(r'<meta name="csrf-token" content="([^"]+)"', page.content.decode())[1]
        self.headers = {"HTTP_X_CSRFTOKEN": self.token}

    def test_all_post_endpoints_reject_missing_and_invalid_tokens(self):
        routes = [
            "api_reload", "api_upload_save", "api_upload_level", "api_live_save_refresh",
            "api_optimize", "api_profile_passives", "api_improve_ivs", "api_base_labels",
            "api_implant_inventory", "api_passive_colors", "api_base_planner",
        ]
        for route in routes:
            for headers in ({}, {"HTTP_X_CSRFTOKEN": "invalid"}):
                with self.subTest(route=route, headers=headers):
                    response = self.client.post(reverse("pals:" + route), data="{}", content_type="application/json", **headers)
                    self.assertEqual(response.status_code, 403)

    def test_json_post_accepts_page_token_and_preserves_payload(self):
        payload = {"target": "Target", "breedAnyway": True}
        with patch.object(breeding, "build_plan", return_value={"ok": True}) as plan:
            response = self.client.post(reverse("pals:api_optimize"), data=json.dumps(payload), content_type="application/json", **self.headers)
        self.assertEqual(response.status_code, 200)
        plan.assert_called_once_with(payload)

    def test_reload_requires_post_and_accepts_token(self):
        self.assertEqual(self.client.get(reverse("pals:api_reload")).status_code, 405)
        with patch.object(data.STORE, "reload") as reload:
            response = self.client.post(reverse("pals:api_reload"), **self.headers)
        self.assertEqual(response.status_code, 200)
        reload.assert_called_once_with()

    def test_multipart_upload_preserves_binary_bytes_and_paths_with_csrf(self):
        payload = b'\x00\xff--boundary-in-data\r\n\n\r'
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(data, "ROOT", root), patch.object(data, "UPLOADS", root), patch.object(saves, "UPLOADS", root), patch.object(saves, "run_decode_from_save_dir", return_value={"ok": True}):
                response = self.client.post(reverse("pals:api_upload_save"), data={
                    "files": [SimpleUploadedFile("player.sav", payload), SimpleUploadedFile("empty.sav", b'')],
                    "relativePaths": json.dumps(["Players/player.sav", "empty.sav"]),
                    "note": "ignored",
                }, **self.headers)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(next(root.rglob("player.sav")).read_bytes(), payload)
                self.assertEqual(next(root.rglob("player.sav")).parent.name, "Players")
                self.assertEqual(next(root.rglob("empty.sav")).read_bytes(), b'')

    def test_raw_level_upload_accepts_csrf_token(self):
        payload = b'\x00\xff\r\n'
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(data, "UPLOADS", root), patch.object(saves, "run_decode_from_level", return_value={"ok": True}):
                response = self.client.post(reverse("pals:api_upload_level"), data=payload, content_type="application/octet-stream", **self.headers)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(next(root.glob("*.sav")).read_bytes(), payload)
