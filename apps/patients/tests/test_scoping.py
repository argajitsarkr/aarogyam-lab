"""Acceptance criteria for centre scoping and the master patient record."""
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.patients.models import Patient, Visit
from apps.factories import PatientFactory, TestCatalogFactory, VisitFactory

pytestmark = pytest.mark.django_db


def register_payload(phone="9812345678", name="Rina Debbarma", test_ids=(), extra=None):
    data = {
        "p-phone": phone, "p-full_name": name, "p-age_years": "52", "p-sex": "F", "p-city": "Agartala",
        "p-district": "West Tripura", "p-state": "Tripura", "p-pin_code": "799001", "p-locality": "Banamalipur",
        "p-consent_to_contact": "on",
        "v-visit_date": timezone.localdate().isoformat(), "v-sample_collection_type": "CENTRE",
        "v-discount": "0", "v-amount_paid": "450", "v-payment_mode": "CASH",
        "v-tests": [str(t) for t in test_ids],
    }
    data.update(extra or {})
    return data


@pytest.fixture
def hba1c(db):
    return TestCatalogFactory(code="HBA1C", name="HbA1c", price=450, retest_interval_days=90, is_chronic_monitoring=True)


def test_rrm_employee_registration_flow(client, employee, centres, hba1c):
    rrm_emp = employee("RRM")
    client.force_login(rrm_emp)
    resp = client.post(reverse("patients:register_new"), register_payload(test_ids=[hba1c.pk]))
    assert resp.status_code == 302, resp.content
    patient = Patient.objects.get(phone="9812345678")
    assert patient.registered_at_centre == centres["RRM"]
    assert patient.patient_id.startswith(f"RRM-{timezone.localdate().year}-")
    visit = patient.visits.get()
    assert visit.centre == centres["RRM"] and visit.total_amount == 450
    assert patient.consent_at is not None


def test_employee_cannot_choose_another_centre(client, employee, centres, hba1c):
    client.force_login(employee("RRM"))
    client.post(reverse("patients:register_new"), register_payload(test_ids=[hba1c.pk], extra={"v-centre": centres["ARP"].pk}))
    assert Patient.objects.get().registered_at_centre == centres["RRM"]


def test_patient_not_in_other_centre_default_list(client, employee, centres):
    p = PatientFactory(registered_at_centre=centres["RRM"], full_name="Only Rrm")
    VisitFactory(patient=p, centre=centres["RRM"])
    client.force_login(employee("BHY"))
    resp = client.get(reverse("patients:list"))
    assert resp.status_code == 200
    assert "Only Rrm" not in resp.content.decode()
    client.force_login(employee("RRM"))
    assert "Only Rrm" in client.get(reverse("patients:list")).content.decode()


def test_cross_centre_lookup_shows_minimal_card_and_full_record_is_403(client, employee, centres):
    p = PatientFactory(registered_at_centre=centres["RRM"], full_name="Rina Debbarma", phone="9812345678",
                       house_street="12 Secret Lane")
    VisitFactory(patient=p, centre=centres["RRM"])
    client.force_login(employee("BHY"))

    resp = client.get(reverse("patients:lookup"), {"term": "98123 45678"})
    html = resp.content.decode()
    assert "Rina Debbarma" in html and p.patient_id in html
    assert "12 Secret Lane" not in html  # minimal card only
    assert "Add new visit" in html and "Other centre" in html

    resp = client.get(reverse("patients:detail", args=[p.pk]))
    assert resp.status_code == 403
    assert AuditLog.objects.filter(action="ACCESS_DENIED", object_id=str(p.pk)).exists()
    assert client.get(reverse("patients:visit_detail", args=[p.visits.first().pk])).status_code == 403


def test_granted_access_allows_view_and_logs_cross_centre(client, employee, centres):
    p = PatientFactory(registered_at_centre=centres["RRM"])
    user = employee("BHY")
    user.extra_centres.add(centres["RRM"])
    client.force_login(user)
    assert client.get(reverse("patients:detail", args=[p.pk])).status_code == 200
    assert AuditLog.objects.filter(action="VIEW_CROSS_CENTRE", object_id=str(p.pk), user=user).exists()


def test_return_visit_at_other_centre_keeps_master_record(client, employee, centres, hba1c):
    p = PatientFactory(registered_at_centre=centres["RRM"])
    VisitFactory(patient=p, centre=centres["RRM"])
    original_id = p.patient_id
    arp = employee("ARP")
    client.force_login(arp)
    resp = client.post(reverse("patients:new_visit", args=[p.pk]), {
        "v-visit_date": timezone.localdate().isoformat(), "v-sample_collection_type": "CENTRE", "v-discount": "0",
        "v-amount_paid": "0", "v-payment_mode": "CASH", "v-tests": [hba1c.pk]})
    assert resp.status_code == 302
    p.refresh_from_db()
    assert p.patient_id == original_id
    assert Patient.objects.count() == 1
    assert set(p.visits.values_list("centre__short_code", flat=True)) == {"RRM", "ARP"}
    # ARP employee can now open the full record (patient visited their centre)
    assert client.get(reverse("patients:detail", args=[p.pk])).status_code == 200


def test_patient_ids_are_sequential_per_centre(centres):
    a = PatientFactory(registered_at_centre=centres["ARP"])
    b = PatientFactory(registered_at_centre=centres["ARP"])
    c = PatientFactory(registered_at_centre=centres["BHY"])
    y = timezone.localdate().year
    assert a.patient_id == f"ARP-{y}-000001"
    assert b.patient_id == f"ARP-{y}-000002"
    assert c.patient_id == f"BHY-{y}-000001"


def test_employee_cannot_edit_other_centres_visit(client, employee, centres):
    p = PatientFactory(registered_at_centre=centres["RRM"])
    v = VisitFactory(patient=p, centre=centres["RRM"])
    user = employee("BHY")
    user.extra_centres.add(centres["RRM"])  # read access only
    client.force_login(user)
    resp = client.post(reverse("patients:visit_detail", args=[v.pk]), {"t-TOTAL_FORMS": "0", "t-INITIAL_FORMS": "0"})
    assert resp.status_code == 403


def test_patients_excel_export_is_gone(client, admin_user):
    from django.urls import NoReverseMatch

    client.force_login(admin_user)
    for name in ("patients:export", "patients:data_export", "patients:erase", "patients:report"):
        with pytest.raises(NoReverseMatch):
            reverse(name)


def test_soft_delete_hides_patient(client, admin_user, centres):
    p = PatientFactory(registered_at_centre=centres["ARP"], full_name="Archive Me")
    client.force_login(admin_user)
    client.post(reverse("patients:delete", args=[p.pk]))
    assert Patient.objects.filter(pk=p.pk).exists()
    assert p not in client.get(reverse("patients:list")).context["object_list"]


def test_visit_soft_delete_excluded_from_scope(centres):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    v = VisitFactory(patient=p, centre=centres["BHY"])
    assert Patient.objects.visible_in_centres([centres["BHY"].pk]).filter(pk=p.pk).exists()
    v.soft_delete()
    assert not Patient.objects.visible_in_centres([centres["BHY"].pk]).filter(pk=p.pk).exists()
    assert Visit.objects.filter(pk=v.pk).exists()
