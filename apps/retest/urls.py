from django.urls import path

from . import views

app_name = "retest"
urlpatterns = [
    path("", views.CandidateListView.as_view(), name="list"),
    path("my-calls/", views.my_calls, name="my_calls"),
    path("run/", views.run_generator, name="run"),
    path("analytics/", views.analytics, name="analytics"),
    path("<int:pk>/log/", views.log_outcome, name="log"),
    path("<int:pk>/move/", views.candidate_move, name="move"),
]
