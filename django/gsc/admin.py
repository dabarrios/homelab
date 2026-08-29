from django.contrib import admin

from .models import GameServer


@admin.register(GameServer)
class GameServerAdmin(admin.ModelAdmin):
    list_display = ("game", "world_name", "version", "container_name", "port", "is_active")
    search_fields = ("game", "world_name", "version", "container_name")
    list_filter = ("game", "is_active")
    readonly_fields = (
        "game",
        "world_name",
        "slug",
        "container_name",
        "allocated_memory",
        "version",
        "port",
        "is_active",
        "notes",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
