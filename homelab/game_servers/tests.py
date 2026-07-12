from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import GameServer

class GameServerModelTest(TestCase):
    def setUp(self):
        # Creating a GameServer object and storing it inside self.server
        self.server = GameServer.objects.create(
            game="Minecraft",
            world_name="Test World",
            slug="test-world",
            container_name="test-container",
            allocated_memory=4,
            version="1.20",
            port=25570,
            is_active=True,
            notes="Test notes",
        )
        self.user = get_user_model().objects.create_user(username="tester", password="test-password")
        self.client.force_login(self.user)
    
    def test_str(self):
        # GameServer has a __str__ method that makes GameServer objects be referenced as their world_name
        self.assertEqual(str(self.server), "Test World")
        
    def test_detail_page_loads(self):
        # Here is the URL name game_server_detail and here is the argument, build the URL for me.
        url = reverse("game_server_detail", args=[self.server.slug])
        # Pretend a browser visits this URL
        response = self.client.get(url)
        # Check if Django successfully returned that page AKA returned status code 200
        self.assertEqual(response.status_code, 200)
        # Check if the correct server info was shown on the page
        self.assertContains(response, "Test World")
        
    def test_dashboard_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_dashboard_page_loads(self):
        url = reverse("dashboard")   # Build dashboard URL
        response = self.client.get(url)     # Simulates user accessing that URL
        self.assertEqual(response.status_code, 200) # Confirms the dashboard GET request succeeded
        
    def test_bad_slug_loads(self):
        url = reverse("game_server_detail", args=["does-not-exist"])    # Build game_server_detail URL with invalid slug
        response = self.client.get(url)                                 # Simulates user accessing that URL
        self.assertEqual(response.status_code, 404)                     # Checks if reaching that URL was a failure (404)
