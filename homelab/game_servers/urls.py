from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.game_server_list, name='game_server_list'),
    path('details/<str:slug>/', views.game_server_detail, name='game_server_detail'),
    path('edit/<str:slug>', views.game_server_edit_detail, name='game_server_edit_detail'),
]