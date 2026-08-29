from django.urls import path
from . import views
from django import pals

urlpatterns = [
    path('', views.home, name='home'),
    path('breeding/', views.breeding, name='breeding'),
    path('ivs/', views.ivs, name='ivs'),
    path('work/', views.work, name='work'),
    path('base-planner/', views.base_planner, name='base_planner'),
]