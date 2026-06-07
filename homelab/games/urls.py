from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.game_status)
]