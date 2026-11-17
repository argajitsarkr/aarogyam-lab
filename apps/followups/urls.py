from django.urls import path

from . import views

app_name = "followups"
urlpatterns = [
    path("", views.FollowUpListView.as_view(), name="list"),
    path("new/", views.followup_create, name="create"),
    path("<int:pk>/", views.followup_detail, name="detail"),
    path("<int:pk>/edit/", views.followup_edit, name="edit"),
    path("<int:pk>/move/", views.followup_move, name="move"),
]
