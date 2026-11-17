from django.urls import path

from . import views

app_name = "dashboard"
urlpatterns = [
    path("", views.home, name="home"),
    path("compare/", views.compare, name="compare"),
    path("map/", views.map_view, name="map"),
]
