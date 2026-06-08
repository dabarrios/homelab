from django.db import models

class GameServer(models.Model):
    game = models.CharField(max_length=255, db_column='GAME', verbose_name="Game")
    name = models.CharField(max_length=255, db_column='NAME', verbose_name="Name")
    slug = models.SlugField(unique=True, db_column='SLUG', verbose_name="Slug")
    allocated_memory = models.CharField(max_length=255, db_column='ALLOCATED_MEMORY', verbose_name="Allocated Memory")
    version = models.CharField(max_length=255, blank=True, db_column='VERSION', verbose_name="Version")
    port = models.PositiveIntegerField(null=True, blank=True, db_column='PORT', verbose_name="Port")
    is_active = models.BooleanField(default=False, db_column='IS_ACTIVE', verbose_name="Is Active?")
    notes = models.TextField(blank=True, db_column='NOTES', verbose_name="Notes")

    # Controls how GameServer objects are displayed by using the name field as its string representation.
    def __str__(self):
        return self.name
    
    class Meta:
        # Human-readable singular name. Django uses it for: Add game server, Change game server, etc.
        verbose_name = 'game server'
        # Human-readable plural name. Django uses it for the label in left-side panel under the header. "Game servers + Add"
        verbose_name_plural = 'game servers'