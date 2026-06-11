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
        # Check if the correct server info was shown on the page
        self.assertContains(response, "Test World")
        
    def test_server_list_page_loads(self):
        url = reverse("game_server_list")   # Build game_server_list URL
        response = self.client.get(url)     # Simulates user accessing that URL
        self.assertEqual(response.status_code, 200) # Checks if reaching that URL was successful (POST)
        
    def test_bad_slug_loads(self):
        url = reverse("game_server_detail", args=["does-not-exist"])    # Build game_server_detail URL with invalid slug
        response = self.client.get(url)                                 # Simulates user accessing that URL
        self.assertEqual(response.status_code, 404)                     # Checks if reaching that URL was a failure (404)
        
    def test_edit_page_updates(self):
        url = reverse("game_server_edit_detail", args=[self.server.slug])   # Build edit_detail URL
        # self.client.post simulates user submitting form
        # The view itself will validate the form
        response = self.client.post(url, {
            "game": "Minecraft",                                            
            "world_name": "Test World",
            "slug": "test-world",
            "container_name": "test-container",
            "allocated_memory": 4,
            "version": "1.20",
            "port": 25570,
            "is_active": "on",
            "notes": "Changed notes",
        })
        
        # 302 redirects; After a successful form save, redirect(server)
        # REMINDER: When we use redirect(server) Django will look at that object and look for a get_absolute_url()
        self.assertEqual(response.status_code, 302) 
        # Reload this object from DB so that we can see what the view saved
        # We do not use self.server.save() because that would be US saving it.
        # We are testing whether the form saved the change.
        self.server.refresh_from_db()
        # Check that this GameServer object's notes field = "Changed notes"
        self.assertEqual(self.server.notes, "Changed notes")     
        