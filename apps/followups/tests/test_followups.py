import datetime as dt

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.factories import PatientFactory, TestCatalogFactory, UserFactory, VisitFactory, VisitTestFactory
from apps.followups.models import ContactNote, FollowUp
from apps.patients.services import create_visit

pytestmark = pytest.mark.django_db


def test_abnormal_flag_creates_followup(centres):
    staff = UserFactory(home_centre=centres["RRM"])
    vt = VisitTestFactory(visit=VisitFactory(patient=PatientFactory(registered_at_centre=centres["RRM"])))
    vt.result_status, vt.flag = "REPORTED", "ABNORMAL"
    vt.save()
    fu = FollowUp.objects.get()
    assert fu.reason == "ABNORMAL_RESULT" and fu.priority == "HIGH"
    assert fu.centre == centres["RRM"] and fu.assigned_to == staff and fu.source_test == vt
    vt.save()  # re-saving does not duplicate
    assert FollowUp.objects.count() == 1


def test_old_imported_abnormal_results_do_not_spam(centres):
    old = timezone.localdate() - dt.timedelta(days=200)
    VisitTestFactory(visit=VisitFactory(patient=PatientFactory(registered_at_centre=centres["ARP"]), visit_date=old),
                     result_status="REPORTED", report_date=old, flag="ABNORMAL")
    assert not FollowUp.objects.exists()


def test_followup_auto_closes_on_return_visit(centres):
    staff = UserFactory(home_centre=centres["ARP"])
    patient = PatientFactory(registered_at_centre=centres["ARP"])
    fu = FollowUp.objects.create(patient=patient, centre=centres["ARP"], reason="DOCTOR_REFERRAL",
                                 status="SCHEDULED", scheduled_date=timezone.localdate())
    closed_before = FollowUp.objects.create(patient=patient, centre=centres["ARP"], status="NOT_INTERESTED")
    visit = create_visit(patient=patient, user=staff, centre=centres["BHY"], tests=[TestCatalogFactory()], visit_fields={})
    fu.refresh_from_db()
    closed_before.refresh_from_db()
    assert fu.status == "COMPLETED" and fu.completed_visit == visit and fu.completed_at
    assert closed_before.status == "NOT_INTERESTED"
    assert ContactNote.objects.filter(followup=fu, status_to="COMPLETED").exists()


def test_manual_create_and_schedule(client, employee, centres):
    user = employee("ARP")
    patient = PatientFactory(registered_at_centre=centres["ARP"])
    client.force_login(user)
    resp = client.post(reverse("followups:create") + f"?patient={patient.pk}", {
        "patient": patient.pk, "reason": "DOCTOR_REFERRAL", "due_date": timezone.localdate().isoformat(), "priority": "MEDIUM"})
    assert resp.status_code == 302
    fu = FollowUp.objects.get()
    assert fu.centre == centres["ARP"] and fu.assigned_to == user  # auto-assigned (only employee)
    when = timezone.localdate() + dt.timedelta(days=3)
    client.post(reverse("followups:detail", args=[fu.pk]), {"status": "SCHEDULED", "scheduled_date": when.isoformat(),
                                                             "scheduled_centre": centres["ARP"].pk, "note": "Booked"})
    fu.refresh_from_db()
    assert fu.status == "SCHEDULED" and fu.scheduled_date == when


def test_scheduled_requires_date(client, employee, centres):
    fu = FollowUp.objects.create(patient=PatientFactory(registered_at_centre=centres["ARP"]), centre=centres["ARP"])
    client.force_login(employee("ARP"))
    client.post(reverse("followups:detail", args=[fu.pk]), {"status": "SCHEDULED"})
    fu.refresh_from_db()
    assert fu.status == "PENDING"


def test_kanban_move_and_scoping(client, employee, centres):
    fu = FollowUp.objects.create(patient=PatientFactory(registered_at_centre=centres["ARP"]), centre=centres["ARP"])
    client.force_login(employee("BHY"))
    assert client.post(reverse("followups:move", args=[fu.pk]), {"status": "CONTACTED"}).status_code == 403
    client.force_login(employee("ARP"))
    assert client.post(reverse("followups:move", args=[fu.pk]), {"status": "CONTACTED"}).status_code == 204
    fu.refresh_from_db()
    assert fu.status == "CONTACTED"


def test_queue_tabs(client, employee, centres):
    p = PatientFactory(registered_at_centre=centres["ARP"], full_name="Overdue Olu")
    FollowUp.objects.create(patient=p, centre=centres["ARP"], due_date=timezone.localdate() - dt.timedelta(days=3))
    client.force_login(employee("ARP"))
    assert "Overdue Olu" in client.get(reverse("followups:list"), {"tab": "overdue", "view": "table"}).content.decode()
    assert "Overdue Olu" not in client.get(reverse("followups:list"), {"tab": "due_today", "view": "table"}).content.decode()


def test_list_renders_in_kanban_and_calendar(client, employee, centres):
    # The kanban/calendar context now comes from the shared KanbanCalendarMixin.
    p = PatientFactory(registered_at_centre=centres["ARP"], full_name="Board Bina")
    FollowUp.objects.create(patient=p, centre=centres["ARP"])
    client.force_login(employee("ARP"))
    kb = client.get(reverse("followups:list"), {"view": "kanban"})
    assert kb.status_code == 200 and "kanban" in kb.context
    assert "Board Bina" in kb.content.decode()
    cal = client.get(reverse("followups:list"), {"view": "calendar"})
    assert cal.status_code == 200 and "cal" in cal.context
