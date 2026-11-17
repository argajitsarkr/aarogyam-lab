from django.urls import path

from . import views

app_name = "pricing"
urlpatterns = [
    path("", views.compare, name="compare"),
    path("lookup/", views.lookup, name="lookup"),
    path("package/", views.package, name="package"),
    path("manage/", views.manage, name="manage"),
    path("manage/save/", views.save_grid, name="save_grid"),
    path("manage/verify/<int:test_id>/", views.mark_verified, name="mark_verified"),
    path("manage/upload/", views.bulk_upload, name="bulk_upload"),
    path("manage/template/", views.template_download, name="template"),
    path("competitors/new/", views.CompetitorCreateView.as_view(), name="competitor_create"),
    path("competitors/<int:pk>/edit/", views.CompetitorUpdateView.as_view(), name="competitor_update"),
]
