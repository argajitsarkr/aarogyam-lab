from django.urls import path

from . import views

app_name = "centres"
urlpatterns = [
    path("", views.CentreListView.as_view(), name="list"),
    path("new/", views.CentreCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", views.CentreUpdateView.as_view(), name="update"),
]
