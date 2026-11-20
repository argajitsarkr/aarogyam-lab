"""The staff side of the public site: the enquiry queue. Included under
/staff/enquiries/ in config/urls.py, so the login gate covers it."""
from django.urls import path

from . import staff_views

app_name = "enquiries"
urlpatterns = [
    path("", staff_views.EnquiryListView.as_view(), name="list"),
    # Reviews share this include (mounted at /staff/enquiries/): the QR sheet to
    # print, and the moderation list. Declared before the <int:pk> enquiry
    # detail so "reviews" is not read as an enquiry id.
    path("reviews/", staff_views.ReviewListView.as_view(), name="reviews"),
    path("reviews/qr/", staff_views.ReviewQRView.as_view(), name="review_qr"),
    path("<int:pk>/", staff_views.EnquiryDetailView.as_view(), name="detail"),
    path("<int:pk>/prescription/", staff_views.prescription_download, name="prescription"),
]
