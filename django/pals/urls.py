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
    path("api/options", views.options, name="api_options"),
    path("api/work-suitability", views.work_suitability, name="api_work_suitability"),
    path("api/ranch-drops", views.ranch_drops, name="api_ranch_drops"),
    path("api/base-work-sites", views.base_work_sites, name="api_base_work_sites"),
    path("api/owned-target-pals", views.owned_target_pals, name="api_owned_target_pals"),
    path("api/reload", views.reload_data, name="api_reload"),
    path("api/live-save/status", views.live_save_status, name="api_live_save_status"),
    path("api/upload-save", views.upload_save, name="api_upload_save"),
    path("api/upload-level", views.upload_level, name="api_upload_level"),
    path("api/live-save/refresh", views.live_save_refresh, name="api_live_save_refresh"),
    path("api/optimize", views.optimize, name="api_optimize"),
    path("api/profile-passives", views.profile_passives, name="api_profile_passives"),
    path("api/improve-ivs", views.improve_ivs, name="api_improve_ivs"),
    path("api/base-labels", views.base_labels, name="api_base_labels"),
    path("api/implant-inventory", views.implant_inventory, name="api_implant_inventory"),
    path("api/base-planner", views.base_planner, name="api_base_planner"),
    path("assets/pals/<path:name>", views.pal_asset, name="pal_asset"),
]
