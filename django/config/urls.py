from django.conf import settings
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("gsc/", include("gsc.urls")),
    path("pals/", include("pals.urls")),
]

if settings.DEBUG_TOOLBAR_AVAILABLE:
    urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))
