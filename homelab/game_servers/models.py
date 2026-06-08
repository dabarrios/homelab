from django.db import models

class GameServer(models.Model):
    game = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    version = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'game server'
        verbose_name_plural = 'game servers'