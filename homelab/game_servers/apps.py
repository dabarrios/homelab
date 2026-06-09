from django.apps import AppConfig


class GameServerConfig(AppConfig):
    # Django's internal name for the app
    name = 'game_servers' 
    # Human-readable name for the app, used in the admin interface in the left-side panel header
    verbose_name = 'Game Servers'