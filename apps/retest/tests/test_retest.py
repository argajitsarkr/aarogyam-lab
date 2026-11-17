import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.factories import PatientFactory, TestCatalogFactory, UserFactory, VisitFactory, VisitTestFactory, reported_test
from apps.followups.models import FollowUp
from apps.patients.services import create_visit
from apps.retest.models import CallLog, RetestCandidate
from apps.retest.services import generate_candidates, log_call

pytestmark = pytest.mark.django_db


@pytest.fixture
def hba1c(db):
    return TestCatalogFactory(code="HBA1C", name="HbA1c", price=450, retest_interval_days=90, is_chronic_monitoring=True)


@pytest.fixture
def staff(centres):
    return UserFactory(home_centre=centres["ARP"])


def test_hba1c_85_days_ago_is_queued(centres, hba1c, staff):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    reported_test(p, hba1c, days_ago=85)
    assert generate_candidates() == 1
    c = RetestCandidate.objects.get()
    assert c.patient == p and c.centre == centres["ARP"]
    assert c.due_date == timezone.localdate() + dt.timedelta(days=5)
    assert c.assigned_to == staff


def test_not_yet_due_is_not_queued(centres, hba1c):
    reported_test(PatientFactory(registered_at_centre=centres["ARP"]), hba1c, days_ago=60)
    assert generate_candidates() == 0


def test_repeated_at_any_centre_excluded(centres, hba1c):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    reported_test(p, hba1c, days_ago=200)
    reported_test(p, hba1c, days_ago=10, centre=centres["BHY"])  # repeated elsewhere
    assert generate_candidates() == 0


def test_no_consent_and_do_not_call_excluded(centres, hba1c):
    reported_test(PatientFactory(registered_at_centre=centres["ARP"], consent_to_contact=False), hba1c, days_ago=85)
    reported_test(PatientFactory(registered_at_centre=centres["ARP"], do_not_call=True), hba1c, days_ago=85)
    assert generate_candidates() == 0


def test_generation_is_idempotent(centres, hba1c):
    reported_test(PatientFactory(registered_at_centre=centres["ARP"]), hba1c, days_ago=100)
    assert generate_candidates() == 1
    assert generate_candidates() == 0


def test_assigned_to_centre_of_last_test(centres, hba1c):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    reported_test(p, hba1c, days_ago=95, centre=centres["RRM"])
    generate_candidates()
    assert RetestCandidate.objects.get().centre == centres["RRM"]


def test_priority_order(centres, hba1c):
    other = TestCatalogFactory(code="VITD", retest_interval_days=90, is_chronic_monitoring=False)
    p1, p2, p3, p4 = (PatientFactory(registered_at_centre=centres["ARP"]) for _ in range(4))
    reported_test(p1, other, days_ago=100)                       # other
    reported_test(p2, hba1c, days_ago=100)                       # chronic
    reported_test(p3, other, days_ago=90, flag="BORDERLINE")     # borderline
    reported_test(p4, other, days_ago=90, flag="ABNORMAL")       # abnormal
    generate_candidates()
    order = list(RetestCandidate.objects.order_by("-priority_score").values_list("patient", flat=True))
    assert order == [p4.pk, p3.pk, p2.pk, p1.pk]


def test_round_robin_assignment(centres, hba1c):
    a = UserFactory(home_centre=centres["ARP"])
    b = UserFactory(home_centre=centres["ARP"])
    for _ in range(4):
        reported_test(PatientFactory(registered_at_centre=centres["ARP"]), hba1c, days_ago=95)
    generate_candidates()
    counts = {u: RetestCandidate.objects.filter(assigned_to=u).count() for u in (a, b)}
    assert counts == {a: 2, b: 2}


def test_do_not_call_suppresses_patient(centres, hba1c, staff):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    reported_test(p, hba1c, days_ago=95)
    generate_candidates()
    log_call(RetestCandidate.objects.get(), staff, CallLog.Outcome.DO_NOT_CALL)
    p.refresh_from_db()
    assert p.do_not_call
    assert not RetestCandidate.objects.open().exists()
    # Future scans never re-add them
    other = TestCatalogFactory(code="LIPID", retest_interval_days=180)
    reported_test(p, other, days_ago=200)
    assert generate_candidates() == 0


def test_booked_then_return_visit_converts(centres, hba1c, staff):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    reported_test(p, hba1c, days_ago=95)
    generate_candidates()
    cand = RetestCandidate.objects.get()
    log_call(cand, staff, CallLog.Outcome.BOOKED, booked_date=timezone.localdate() + dt.timedelta(days=1))
    cand.refresh_from_db()
    assert cand.status == "SCHEDULED"
    fu = FollowUp.objects.get(reason="RE_TEST")
    assert fu.status == "SCHEDULED"

    # Patient comes back at a different centre for the test
    visit = create_visit(patient=p, user=staff, centre=centres["BHY"], tests=[hba1c], visit_fields={})
    cand.refresh_from_db()
    fu.refresh_from_db()
    assert cand.status == "CONVERTED" and cand.converted_visit == visit
    assert CallLog.objects.get(outcome="BOOKED").converted
    assert fu.status == "COMPLETED" and fu.completed_visit == visit


def test_my_call_list_shows_only_own_and_logs_outcome(client, centres, hba1c, staff):
    other = UserFactory(home_centre=centres["ARP"])
    p = PatientFactory(registered_at_centre=centres["ARP"], full_name="Call Me", phone="9800000001")
    reported_test(p, hba1c, days_ago=95)
    generate_candidates()
    cand = RetestCandidate.objects.get()
    owner = cand.assigned_to
    not_owner = other if owner == staff else staff
    client.force_login(not_owner)
    assert "Call Me" not in client.get(reverse("retest:my_calls")).content.decode()
    client.force_login(owner)
    html = client.get(reverse("retest:my_calls")).content.decode()
    assert "Call Me" in html and 'href="tel:9800000001"' in html
    resp = client.post(reverse("retest:log", args=[cand.pk]), {"outcome": "CALL_BACK",
                                                                "callback_date": (timezone.localdate() + dt.timedelta(days=3)).isoformat()},
                       HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    cand.refresh_from_db()
    assert cand.status == "CONTACTED" and cand.attempts == 1


def test_other_centre_cannot_log_call(client, centres, hba1c, employee):
    reported_test(PatientFactory(registered_at_centre=centres["ARP"]), hba1c, days_ago=95)
    generate_candidates()
    client.force_login(employee("BHY"))
    resp = client.post(reverse("retest:log", args=[RetestCandidate.objects.get().pk]), {"outcome": "NO_ANSWER"})
    assert resp.status_code == 403


def test_analytics_admin_only(client, admin_user, employee):
    client.force_login(employee("ARP"))
    assert client.get(reverse("retest:analytics")).status_code == 403
    client.force_login(admin_user)
    assert client.get(reverse("retest:analytics")).status_code == 200


def test_unreported_tests_ignored(centres, hba1c):
    p = PatientFactory(registered_at_centre=centres["ARP"])
    visit = VisitFactory(patient=p, visit_date=timezone.localdate() - dt.timedelta(days=100))
    VisitTestFactory(visit=visit, test=hba1c)  # still PENDING
    assert generate_candidates() == 0
