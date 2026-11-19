"""The staff side of the public site: the enquiry queue. Included under
/staff/enquiries/ in config/urls.py, so the login gate covers it."""
from django.urls import path

from . import staff_views

app_name = "enquiries"
urlpatterns = [
    path("", staff_views.EnquiryListView.as_view(), name="list"),
    path("<int:pk>/", staff_views.EnquiryDetailView.as_view(), name="detail"),
    path("<int:pk>/prescription/", staff_views.prescription_download, name="prescription"),
]
