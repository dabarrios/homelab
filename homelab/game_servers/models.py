from django.db import models

class GameServer(models.Model):
    game = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    version = models.CharField(max_length=255, blank=True)
    port = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    # Controls how GameServer objects are displayed by using the name field as its string representation.
    def __str__(self):
        return self.name
    
    class Meta:
        # Human-readable singular name. Django uses it for: Add game server, Change game server, etc.
        verbose_name = 'game server'
        # Human-readable plural name. Django uses it for the label in the admin interface.
        verbose_name_plural = 'game servers'