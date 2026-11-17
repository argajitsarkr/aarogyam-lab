from django.urls import path

from . import views

app_name = "patients"
urlpatterns = [
    path("", views.PatientListView.as_view(), name="list"),
    path("register/", views.register, name="register"),
    path("register/lookup/", views.lookup, name="lookup"),
    path("register/new/", views.register_new, name="register_new"),
    path("localities/", views.localities, name="localities"),
    path("import/", views.import_upload, name="import"),
    path("import/<str:token>/map/", views.import_map, name="import_map"),
    path("import/<str:token>/preview/", views.import_preview, name="import_preview"),
    path("<int:pk>/", views.patient_detail, name="detail"),
    path("<int:pk>/edit/", views.PatientUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.patient_soft_delete, name="delete"),
    path("<int:pk>/visits/new/", views.new_visit, name="new_visit"),
    path("visits/<int:pk>/", views.visit_detail, name="visit_detail"),
    path("doctors/", views.DoctorListView.as_view(), name="doctors"),
    path("doctors/new/", views.DoctorCreateView.as_view(), name="doctor_create"),
    path("doctors/<int:pk>/edit/", views.DoctorUpdateView.as_view(), name="doctor_update"),
    path("tests/", views.TestListView.as_view(), name="tests"),
    path("tests/new/", views.TestCreateView.as_view(), name="test_create"),
    path("tests/<int:pk>/edit/", views.TestUpdateView.as_view(), name="test_update"),
    path("tests/json/", views.tests_json, name="tests_json"),
]
