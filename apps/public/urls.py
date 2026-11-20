from django.urls import path

from . import views

app_name = "public"
urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),

    path("centres/", views.CentreListView.as_view(), name="centres"),
    path("centres/<slug:slug>/", views.CentreDetailView.as_view(), name="centre"),
    path("doctors/", views.DoctorListView.as_view(), name="doctors"),

    path("lab-tests/", views.TestListView.as_view(), name="tests"),
    path("lab-tests/concern/<slug:slug>/", views.ConcernView.as_view(), name="concern"),
    path("lab-tests/<str:code>/", views.TestDetailView.as_view(), name="test"),

    path("medicines/", views.MedicineHomeView.as_view(), name="medicines"),
    path("medicines/<slug:slug>/", views.MedicineCategoryView.as_view(), name="medicine_category"),
    path("upload-prescription/", views.PrescriptionUploadView.as_view(), name="prescription"),

    path("about/", views.AboutView.as_view(), name="about"),
    path("contact/", views.ContactView.as_view(), name="contact"),

    # The QR code at each centre opens this with ?c=<short_code>. GET shows the
    # star form, POST records the rating.
    path("review/", views.ReviewCreateView.as_view(), name="review"),

    # The one endpoint every call-to-action posts to. HTMX swaps the form for a
    # thank-you panel; without JS it redirects to the same page with a message.
    path("enquiry/", views.EnquiryCreateView.as_view(), name="enquiry"),
]
