from django.contrib import admin
from .models import GameServer

@admin.register(GameServer)
class GameServerAdmin(admin.ModelAdmin):
    list_display = ('game', 'world_name', 'version', 'container_name', 'port', 'is_active')
    search_fields = ('game', 'world_name', 'version')
    list_filter = ('game','is_active')