from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('details/<str:slug>/', views.game_server_detail, name='game_server_detail'),
]