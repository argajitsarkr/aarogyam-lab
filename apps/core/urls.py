from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("scope/", views.set_scope, name="set_scope"),
    path("prefs/", views.save_pref, name="save_pref"),
    path("saved-filters/", views.saved_filter_create, name="saved_filter_create"),
    path("saved-filters/<int:pk>/delete/", views.saved_filter_delete, name="saved_filter_delete"),
    path("saved-filters/<int:pk>/pin/", views.saved_filter_toggle_pin, name="saved_filter_pin"),
    path("settings/", views.SiteSettingsView.as_view(), name="settings"),
]
