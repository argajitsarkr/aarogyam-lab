"""A visit can be registered before anyone knows which tests were run, and the
tests can be added to it afterwards."""
import pytest
from django.urls import reverse

from apps.factories import PatientFactory, TestCatalogFactory, VisitFactory
from apps.patients.models import Visit, VisitTest

pytestmark = pytest.mark.django_db


def _register_payload(**over):
    """Mirrors apps/patients/tests/test_scoping.register_payload, minus the tests."""
    from django.utils import timezone

    data = {
        "p-phone": "9876500011", "p-full_name": "No Tests Yet", "p-age_years": "40", "p-sex": "M",
        "p-city": "Agartala", "p-district": "West Tripura", "p-state": "Tripura",
        "p-pin_code": "799001", "p-locality": "Banamalipur", "p-consent_to_contact": "on",
        "v-visit_date": timezone.localdate().isoformat(), "v-sample_collection_type": "CENTRE",
    }
    data.update(over)
    return data


class TestRegisteringWithoutTests:
    def test_a_visit_with_no_tests_is_accepted(self, client, employee, centres):
        client.force_login(employee("ARP"))
        resp = client.post(reverse("patients:register_new"), _register_payload())
        assert resp.status_code == 302, resp.content[:400]
        visit = Visit.objects.get()
        assert visit.tests.count() == 0
        assert visit.centre == centres["ARP"]

    def test_tests_can_still_be_given_at_registration(self, client, employee, centres):
        t = TestCatalogFactory()
        client.force_login(employee("ARP"))
        resp = client.post(reverse("patients:register_new"), _register_payload(**{"v-tests": [t.pk]}))
        assert resp.status_code == 302
        assert Visit.objects.get().tests.count() == 1


class TestAddingTestsLater:
    def test_adding_tests_to_an_existing_visit(self, client, employee, centres):
        user = employee("ARP")
        visit = VisitFactory(patient=PatientFactory(registered_at_centre=centres["ARP"]), centre=centres["ARP"])
        a, b = TestCatalogFactory(code="AAA"), TestCatalogFactory(code="BBB")
        client.force_login(user)
        resp = client.post(reverse("patients:visit_detail", args=[visit.pk]),
                           {"add_tests": "1", "tests": [a.pk, b.pk]})
        assert resp.status_code == 302
        assert set(visit.tests.values_list("test__code", flat=True)) == {"AAA", "BBB"}

    def test_a_test_already_on_the_visit_is_not_offered_twice(self, client, employee, centres):
        user = employee("ARP")
        visit = VisitFactory(patient=PatientFactory(registered_at_centre=centres["ARP"]), centre=centres["ARP"])
        already = TestCatalogFactory(code="DUP")
        VisitTest.objects.create(visit=visit, test=already)
        client.force_login(user)
        html = client.get(reverse("patients:visit_detail", args=[visit.pk])).content.decode()
        assert f'<option value="{already.pk}"' not in html

    def test_another_centre_cannot_add_tests(self, client, employee, centres):
        visit = VisitFactory(patient=PatientFactory(registered_at_centre=centres["RRM"]), centre=centres["RRM"])
        t = TestCatalogFactory(code="CCC")
        client.force_login(employee("BHY"))
        resp = client.post(reverse("patients:visit_detail", args=[visit.pk]),
                           {"add_tests": "1", "tests": [t.pk]})
        assert resp.status_code == 403
        assert visit.tests.count() == 0

    def test_the_results_grid_still_saves(self, client, employee, centres):
        user = employee("ARP")
        visit = VisitFactory(patient=PatientFactory(registered_at_centre=centres["ARP"]), centre=centres["ARP"])
        vt = VisitTest.objects.create(visit=visit, test=TestCatalogFactory(code="RES"))
        client.force_login(user)
        resp = client.post(reverse("patients:visit_detail", args=[visit.pk]), {
            "t-TOTAL_FORMS": "1", "t-INITIAL_FORMS": "1", "t-MIN_NUM_FORMS": "0", "t-MAX_NUM_FORMS": "1000",
            "t-0-id": str(vt.pk), "t-0-result_status": "REPORTED", "t-0-flag": "NORMAL",
            "t-0-result_summary": "fine", "t-0-report_date": "2026-11-18",
        })
        assert resp.status_code == 302, resp.content[:400]
        vt.refresh_from_db()
        assert vt.result_status == "REPORTED" and vt.flag == "NORMAL"


class TestQuickAdd:
    """A patient treated before this app existed: name and mobile, nothing else."""

    def _payload(self, **over):
        data = {"p-reg_mode": "quick", "p-phone": "9876500022", "p-full_name": "Old Record",
                "v-visit_date": "", "v-sample_collection_type": "CENTRE"}
        data.update(over)
        return data

    def test_name_and_mobile_are_enough(self, client, employee, centres):
        from apps.patients.models import Patient

        client.force_login(employee("ARP"))
        resp = client.post(reverse("patients:register_new"), self._payload())
        assert resp.status_code == 302, resp.content[:500]
        p = Patient.objects.get(phone="9876500022")
        assert p.full_name == "Old Record" and p.sex == "" and p.age_years is None
        assert p.registered_at_centre == centres["ARP"]

    def test_full_mode_still_demands_age_and_sex(self, client, employee, centres):
        client.force_login(employee("ARP"))
        resp = client.post(reverse("patients:register_new"),
                           self._payload(**{"p-reg_mode": "full"}))
        assert resp.status_code == 200  # redisplayed with errors
        form = resp.context["pform"]
        assert "age_years" in form.errors and "sex" in form.errors

    def test_a_missing_mode_is_treated_as_full(self, client, employee, centres):
        """Hiding a field client-side must not be able to relax the rules."""
        payload = self._payload()
        payload.pop("p-reg_mode")
        client.force_login(employee("ARP"))
        resp = client.post(reverse("patients:register_new"), payload)
        assert resp.status_code == 200
        assert "sex" in resp.context["pform"].errors

    def test_the_address_is_down_to_locality_and_pin(self, client, employee):
        from apps.patients.forms import PatientForm

        fields = set(PatientForm().fields)
        assert {"locality", "pin_code"} <= fields
        assert not fields & {"house_street", "village_ward", "city", "district", "state"}

    def test_quick_add_creates_no_visit(self, client, employee, centres):
        from apps.patients.models import Patient, Visit

        client.force_login(employee("ARP"))
        client.post(reverse("patients:register_new"), self._payload(**{"p-phone": "9876500033"}))
        p = Patient.objects.get(phone="9876500033")
        assert Visit.objects.filter(patient=p).count() == 0, "a past patient gets no invented visit"

    def test_admin_on_all_centres_is_told_to_pick_one(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.post(reverse("patients:register_new"), self._payload(**{"p-phone": "9876500044"}))
        assert resp.status_code == 200
        assert "scope switcher" in resp.content.decode()
