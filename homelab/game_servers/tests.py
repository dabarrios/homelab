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
        