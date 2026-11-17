import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.patients.models import Patient, TestCatalog
from apps.retest.services import generate_candidates

pytestmark = pytest.mark.django_db

CSV = (
    "Patient Name,Mobile,Gender,Age,Area,PIN,Visit Date,Tests,Flag\n"
    "Asha Das,9876500001,F,50,Ram Nagar,799002,01-06-2026,HBA1C,Abnormal\n"
    "Bad Phone,12345,M,40,,,,,\n"
    "Asha Das,9876500001,F,50,Ram Nagar,799002,,,\n"
)


def test_import_flow_map_preview_commit(client, admin_user, centres):
    call_command("seed_test_catalog", verbosity=0)
    client.force_login(admin_user)
    resp = client.post(reverse("patients:import"), {"centre": centres["RRM"].pk,
                                                    "file": SimpleUploadedFile("legacy.csv", CSV.encode(), content_type="text/csv")})
    assert resp.status_code == 302
    map_url = resp.url
    resp = client.get(map_url)
    mapping = resp.context["mapping"]
    assert mapping["full_name"] == "Patient Name" and mapping["phone"] == "Mobile" and mapping["test_codes"] == "Tests"
    resp = client.post(map_url, mapping)
    preview_url = resp.url
    resp = client.get(preview_url)
    # third row repeats the first one in the same file -> duplicate, not a second record
    assert resp.context["counts"] == {"ok": 1, "duplicate": 1, "error": 1}
    client.post(preview_url)
    p = Patient.objects.get(phone="9876500001")
    assert p.registered_at_centre == centres["RRM"] and p.patient_id.startswith("RRM-")
    assert p.visits.get().tests.get().test.code == "HBA1C"
    assert AuditLog.objects.filter(action="IMPORT").exists()
    # Imported history feeds the re-test engine (consent column not mapped -> no consent -> not queued)
    assert generate_candidates() == 0


def test_import_admin_only(client, employee):
    client.force_login(employee("ARP"))
    assert client.get(reverse("patients:import")).status_code == 403


def test_demo_data_blocked_without_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="disabled when DEBUG=False"):
        call_command("create_demo_data")


def test_seed_commands_idempotent(db):
    call_command("seed_centres", verbosity=0)
    call_command("seed_centres", verbosity=0)
    call_command("seed_test_catalog", verbosity=0)
    call_command("seed_test_catalog", verbosity=0)
    from apps.centres.models import Centre

    assert Centre.objects.count() == 3
    assert Centre.objects.get(is_head_centre=True).short_code == "ARP"
    assert 45 <= TestCatalog.objects.count() <= 60
    assert TestCatalog.objects.get(code="HBA1C").retest_interval_days == 90
    assert not TestCatalog.objects.filter(needs_clinical_review=False).exists()


def test_demo_data_runs(settings, db):
    settings.DEBUG = True
    call_command("create_demo_data", patients=20, verbosity=0)
    assert Patient.objects.count() == 20
