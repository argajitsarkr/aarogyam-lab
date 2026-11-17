import datetime as dt

from django.db import transaction
from django.utils import timezone

from apps.core.assignment import pick_assignee

from .models import ContactNote, FollowUp


def create_abnormal_followup(visit_test):
    """Auto-create one follow-up per abnormal test result."""
    if FollowUp.objects.filter(source_test=visit_test).exists():
        return None
    visit = visit_test.visit
    return FollowUp.objects.create(
        patient=visit.patient,
        centre=visit.centre,
        source_visit=visit,
        source_test=visit_test,
        reason=FollowUp.Reason.ABNORMAL_RESULT,
        referring_doctor=visit.referring_doctor,
        due_date=timezone.localdate() + dt.timedelta(days=2),
        priority=FollowUp.Priority.HIGH,
        assigned_to=pick_assignee(visit.centre, "assigned_followups", FollowUp.OPEN_STATUSES),
        notes=f"Auto-created: {visit_test.test.name} flagged Abnormal"
              + (f" — {visit_test.result_summary}" if visit_test.result_summary else ""),
    )


@transaction.atomic
def auto_close_on_visit(visit):
    """When the patient returns, close their open follow-ups and link the visit."""
    now = timezone.now()
    qs = FollowUp.objects.open().filter(patient=visit.patient, created_at__lt=visit.created_at).exclude(source_visit=visit)
    for fu in qs.select_for_update():
        old = fu.status
        fu.status = FollowUp.Status.COMPLETED
        fu.completed_visit = visit
        fu.completed_at = now
        fu.save()
        ContactNote.objects.create(followup=fu, user=visit.registered_by, status_from=old, status_to=fu.status,
                                   note=f"Auto-closed: patient returned on {visit.visit_date:%d-%m-%Y} at {visit.centre.name}.")


def change_status(fu, user, status, note="", scheduled_date=None, scheduled_centre=None, next_action_date=None):
    old = fu.status
    fu.status = status
    if status == FollowUp.Status.SCHEDULED:
        fu.scheduled_date = scheduled_date or fu.scheduled_date
        fu.scheduled_centre = scheduled_centre or fu.scheduled_centre or fu.centre
    if status == FollowUp.Status.COMPLETED and not fu.completed_at:
        fu.completed_at = timezone.now()
    if next_action_date is not None:
        fu.next_action_date = next_action_date
    fu.save()
    if old != status or note:
        ContactNote.objects.create(followup=fu, user=user, status_from=old, status_to=status, note=note)
    return fu
