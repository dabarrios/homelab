from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.servers_overview, name='servers_overview'),
    path('status/<str:slug>/', views.server_details, name='server_details'),
]