from django.apps import AppConfig


class GameServerConfig(AppConfig):
    name = 'game_servers'           # Django's internal name for the app
    verbose_name = 'Game Servers'   # Human-readable name for app, used in the admin interface in the left-side panel header