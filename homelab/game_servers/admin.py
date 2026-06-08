from django.contrib import admin
from .models import GameServer

@admin.register(GameServer)
class GameServerAdmin(admin.ModelAdmin):
    list_display = ('game', 'name', 'version', 'port', 'is_active')
    search_fields = ('game', 'name', 'version')
    list_filter = ('is_active',)