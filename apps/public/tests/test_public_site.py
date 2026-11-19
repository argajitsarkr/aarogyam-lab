"""The public site: what a stranger can see, and what they must not.

The security-relevant assertions are the ones to keep if this file is ever
trimmed: an unpublished centre or test must 404, and an uploaded prescription
must not be reachable without a session.
"""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.public.models import Doctor, Enquiry, HealthConcern, MedicineCategory


@pytest.fixture
def published_centre(centres):
    c = centres["ARP"]
    c.is_public = True
    c.address = "Main Road"
    c.contact_phone = "9876543210"
    c.opening_hours = "Mon-Sat  7:00 am - 8:00 pm\nSun  8:00 am - 1:00 pm"
    c.save()
    return c


@pytest.fixture
def published_test(db):
    from apps.patients.models import TestCatalog

    return TestCatalog.objects.create(
        code="TSH1", name="Thyroid Profile", price=400, is_public=True,
        public_description="Checks how your thyroid gland is working.",
        sample_type="Blood", report_in_hours=24,
    )


# ---------------------------------------------------------------- pages render

@pytest.mark.django_db
@pytest.mark.parametrize("name", [
    "public:home", "public:centres", "public:doctors", "public:tests",
    "public:medicines", "public:prescription", "public:about", "public:contact",
])
def test_every_public_page_renders_for_a_stranger(client, name):
    resp = client.get(reverse(name))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_home_lists_published_centres_and_tests(client, published_centre, published_test):
    body = client.get(reverse("public:home")).content.decode()
    assert published_centre.name in body
    assert "Thyroid Profile" in body


@pytest.mark.django_db
def test_centre_page_shows_hours_and_phone(client, published_centre):
    body = client.get(published_centre.get_absolute_url()).content.decode()
    assert "7:00 am - 8:00 pm" in body
    assert "9876543210" in body


# --------------------------------------------------- the published/unpublished line

@pytest.mark.django_db
def test_an_unpublished_centre_is_not_reachable(client, centres):
    private = centres["RRM"]
    assert private.is_public is False
    assert client.get(f"/centres/{private.short_code.lower()}/").status_code == 404
    assert private.name not in client.get(reverse("public:centres")).content.decode()


@pytest.mark.django_db
def test_an_unpublished_test_is_not_reachable(client, published_test):
    published_test.is_public = False
    published_test.save()
    assert client.get(reverse("public:test", args=[published_test.code])).status_code == 404


@pytest.mark.django_db
def test_partner_prices_are_listed_without_a_recommendation(client, published_test):
    """Several partners, no "cheapest", no "you save" - the pricing rule."""
    from apps.pricing.models import Competitor, CompetitorPrice

    for name, price in [("Alpha Labs", 500), ("Beta Diagnostics", 380)]:
        CompetitorPrice.objects.create(
            test=published_test, competitor=Competitor.objects.create(name=name), price=price
        )
    body = client.get(reverse("public:test", args=[published_test.code])).content.decode()
    assert "Alpha Labs" in body and "Beta Diagnostics" in body
    assert "380" in body and "500" in body
    lowered = body.lower()
    for forbidden in ("you save", "cheapest", "best price", "our price", "lowest price"):
        assert forbidden not in lowered, f"the public test page must not say {forbidden!r}"


# ---------------------------------------------------------------- enquiries

@pytest.mark.django_db
def test_a_visitor_can_ask_for_a_call_back(client, published_centre):
    resp = client.post(reverse("public:enquiry"), {
        "kind": "CALLBACK", "name": "Ruma Das", "phone": "98 7654 3210",
        "centre": published_centre.pk, "message": "Please call after 6pm",
    })
    assert resp.status_code == 302
    e = Enquiry.objects.get()
    assert e.name == "Ruma Das"
    assert e.phone == "9876543210", "spaces and groupings should be stripped, not rejected"
    assert e.status == Enquiry.Status.NEW
    assert e.centre == published_centre


@pytest.mark.django_db
def test_a_phone_number_with_the_country_code_is_accepted(client):
    client.post(reverse("public:enquiry"), {"kind": "CALLBACK", "name": "A", "phone": "+91 9876543210"})
    assert Enquiry.objects.get().phone == "9876543210"


@pytest.mark.django_db
def test_the_honeypot_marks_spam_rather_than_dropping_it(client):
    client.post(reverse("public:enquiry"), {
        "kind": "CALLBACK", "name": "bot", "phone": "9876543210", "website": "http://spam.example",
    })
    e = Enquiry.objects.get()
    assert e.status == Enquiry.Status.SPAM, "flagged, but still visible to the staff"


@pytest.mark.django_db
def test_a_prescription_enquiry_needs_a_file(client):
    resp = client.post(reverse("public:enquiry"), {
        "kind": "PRESCRIPTION", "name": "Ruma", "phone": "9876543210",
    }, headers={"hx-request": "true"})
    assert Enquiry.objects.count() == 0
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "attach a photo" in body, "the error has to come back on the page"
    assert 'type="file"' in body, "and so does the file input it is about"


@pytest.mark.django_db
def test_without_javascript_the_errors_come_back_as_messages(client):
    """The no-JS fallback redirects to the page they posted from. Django's own
    form_invalid would re-render with a fresh, unbound form and silently drop
    every error, which is how this went unnoticed the first time."""
    resp = client.post(reverse("public:enquiry"),
                       {"kind": "PRESCRIPTION", "name": "Ruma", "phone": "9876543210",
                        "next": reverse("public:prescription")},
                       follow=True)
    assert Enquiry.objects.count() == 0
    assert "attach a photo" in resp.content.decode()


# ----------------------------------------------------- prescriptions stay private

@pytest.mark.django_db
def test_an_uploaded_prescription_is_not_reachable_without_a_session(client):
    upload = SimpleUploadedFile("rx.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, content_type="image/png")
    client.post(reverse("public:enquiry"), {
        "kind": "PRESCRIPTION", "name": "Ruma", "phone": "9876543210", "prescription": upload,
    })
    enquiry = Enquiry.objects.get()
    assert enquiry.prescription

    # No url on the file itself: private_storage has base_url=None, so there is
    # nothing nginx would serve even if somebody guessed the path.
    with pytest.raises(ValueError):
        enquiry.prescription.url

    resp = client.get(reverse("enquiries:prescription", args=[enquiry.pk]))
    assert resp.status_code in (302, 404), "a stranger must not reach a prescription"


@pytest.mark.django_db
def test_staff_can_open_a_prescription(client, admin_user, settings):
    settings.DEBUG = True
    upload = SimpleUploadedFile("rx.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, content_type="image/png")
    client.post(reverse("public:enquiry"), {
        "kind": "PRESCRIPTION", "name": "Ruma", "phone": "9876543210", "prescription": upload,
    })
    enquiry = Enquiry.objects.get()
    client.force_login(admin_user)
    resp = client.get(reverse("enquiries:prescription", args=[enquiry.pk]))
    assert resp.status_code == 200


# ---------------------------------------------------------------- staff queue

@pytest.mark.django_db
def test_the_enquiry_queue_needs_a_session(client):
    resp = client.get(reverse("enquiries:list"))
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_handling_an_enquiry_records_who_did_it(client, admin_user):
    enquiry = Enquiry.objects.create(kind="CALLBACK", name="Ruma", phone="9876543210")
    client.force_login(admin_user)
    client.post(reverse("enquiries:detail", args=[enquiry.pk]),
                {"status": "CONTACTED", "staff_notes": "Called, booking for Friday"})
    enquiry.refresh_from_db()
    assert enquiry.status == "CONTACTED"
    assert enquiry.handled_by == admin_user
    assert enquiry.handled_at is not None


# ---------------------------------------------------------------- seo

@pytest.mark.django_db
def test_the_sitemap_lists_published_pages_only(client, published_centre, published_test):
    body = client.get("/sitemap.xml").content.decode()
    assert published_centre.get_absolute_url() in body
    assert reverse("public:test", args=[published_test.code]) in body
    assert "/staff/" not in body
    assert "/accounts/" not in body


@pytest.mark.django_db
def test_robots_points_at_the_sitemap(client):
    body = client.get("/robots.txt").content.decode()
    assert "/sitemap.xml" in body
    assert "Disallow: /staff/" in body


# ---------------------------------------------------------------- seeded content

@pytest.mark.django_db
def test_seed_public_content_is_idempotent_and_invents_no_facts():
    from django.core.management import call_command

    out = io.StringIO()
    call_command("seed_public_content", stdout=out)
    first = (HealthConcern.objects.count(), MedicineCategory.objects.count())
    assert first[0] and first[1]

    call_command("seed_public_content", stdout=io.StringIO())
    assert (HealthConcern.objects.count(), MedicineCategory.objects.count()) == first

    # It must not fabricate a doctor, a phone number or a licence.
    from apps.core.models import SiteSettings

    assert Doctor.objects.count() == 0
    s = SiteSettings.load()
    assert s.public_phone == "" and s.pharmacy_licence_no == ""
