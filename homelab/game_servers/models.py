from django.db import models

class GameServer(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    game = models.CharField(max_length=255)
    host = models.CharField(max_length=100, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name