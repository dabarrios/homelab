from django.urls import path
from . import views

app_name = "pals"

urlpatterns = [
    path("", views.home, name="home"),
    path("breeding/", views.breeding, name="breeding"),
    path("ivs/", views.ivs, name="ivs"),
    path("work/", views.work, name="work"),
    path("ranch/", views.ranch, name="ranch"),
    path("bases/", views.bases, name="bases"),
]
