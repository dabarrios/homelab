from django.conf import settings
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", include("game_servers.urls")),
]

if settings.DEBUG_TOOLBAR_AVAILABLE:
    urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
