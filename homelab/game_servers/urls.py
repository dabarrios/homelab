from django.urls import path
from . import views

urlpatterns = [
    path('overview/', views.game_server_list, name='game_server_list'),
    path('details/<str:slug>/', views.game_server_detail, name='game_server_detail'),
    path('edit/<str:slug>', views.game_server_form, name='game_server_form'),
    path('edit/details/<str:slug>', views.update_server_details, name='update_server_details'),
    path('edit/notes/<str:slug>', views.update_server_notes, name='update_server_notes'),
]