"""Re-test candidate generation, call logging and conversion tracking."""
import datetime as dt

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.core.assignment import pick_assignee
from apps.core.models import SiteSettings
from apps.followups.models import FollowUp
from apps.patients.models import VisitTest

from .models import CallLog, RetestCandidate

FLAG_SCORE = {"ABNORMAL": 300, "BORDERLINE": 200}
CHRONIC_SCORE = 100
MAX_OVERDUE_BONUS = 99


def priority_score(flag, is_chronic, due_date, today):
    """Abnormal > Borderline > chronic-monitoring > others, then days overdue."""
    base = FLAG_SCORE.get(flag, CHRONIC_SCORE if is_chronic else 0)
    overdue = max(0, min((today - due_date).days, MAX_OVERDUE_BONUS))
    return base + overdue


def eligible_source_tests(today=None, lookahead_days=None):
    """VisitTests whose re-test falls due within the look-ahead window (or is
    past), for contactable patients, with no repeat of that test since."""
    today = today or timezone.localdate()
    lookahead_days = SiteSettings.load().retest_lookahead_days if lookahead_days is None else lookahead_days
    horizon = today + dt.timedelta(days=lookahead_days)

    repeated_since = VisitTest.objects.filter(
        patient=OuterRef("patient"), test=OuterRef("test"),
        visit__visit_date__gt=OuterRef("visit__visit_date"), visit__deleted_at__isnull=True,
    )
    already_candidate = RetestCandidate.objects.filter(source_test=OuterRef("pk"))
    qs = (
        VisitTest.objects.filter(
            result_status=VisitTest.ResultStatus.REPORTED,
            report_date__isnull=False,
            test__retest_interval_days__isnull=False,
            test__is_active=True,
            visit__deleted_at__isnull=True,
            patient__consent_to_contact=True,
            patient__do_not_call=False,
            patient__deleted_at__isnull=True,
            patient__erased_at__isnull=True,
        )
        .exclude(Exists(repeated_since))
        .exclude(Exists(already_candidate))
        .select_related("test", "visit__centre", "patient")
    )
    for vt in qs.iterator(chunk_size=500):
        due = vt.report_date + dt.timedelta(days=vt.test.retest_interval_days)
        if due <= horizon:
            yield vt, due


def generate_candidates(today=None, lookahead_days=None):
    """Create RetestCandidate rows; returns number created. Idempotent."""
    today = today or timezone.localdate()
    created = 0
    for vt, due in eligible_source_tests(today, lookahead_days):
        # Close older open candidates for the same patient+test (superseded by a newer report).
        RetestCandidate.objects.open().filter(patient=vt.patient, test=vt.test).update(status=RetestCandidate.Status.CLOSED)
        centre = vt.visit.centre
        try:
            with transaction.atomic():
                RetestCandidate.objects.create(
                    patient=vt.patient, centre=centre, source_test=vt, test=vt.test, due_date=due,
                    priority_score=priority_score(vt.flag, vt.test.is_chronic_monitoring, due, today),
                    assigned_to=pick_assignee(centre, "retest_candidates", RetestCandidate.OPEN_STATUSES),
                )
            created += 1
        except IntegrityError:
            continue
    refresh_priorities(today)
    return created


def refresh_priorities(today=None):
    """Daily bump of overdue bonus for open candidates."""
    today = today or timezone.localdate()
    for c in RetestCandidate.objects.open().select_related("source_test", "test"):
        score = priority_score(c.source_test.flag, c.test.is_chronic_monitoring, c.due_date, today)
        if score != c.priority_score:
            RetestCandidate.objects.filter(pk=c.pk).update(priority_score=score)


@transaction.atomic
def log_call(candidate, user, outcome, notes="", callback_date=None, booked_date=None):
    """Record a call and move the candidate through its workflow."""
    O, S = CallLog.Outcome, RetestCandidate.Status
    call = CallLog.objects.create(candidate=candidate, centre=candidate.centre, employee=user, outcome=outcome,
                                  notes=notes, callback_date=callback_date, booked_date=booked_date)
    candidate.attempts += 1
    candidate.last_called_at = call.called_at
    if outcome == O.BOOKED:
        candidate.status = S.SCHEDULED
        candidate.booked_date = booked_date or timezone.localdate()
        FollowUp.objects.create(
            patient=candidate.patient, centre=candidate.centre, reason=FollowUp.Reason.RE_TEST,
            source_visit=candidate.source_test.visit, source_test=candidate.source_test,
            due_date=candidate.booked_date, status=FollowUp.Status.SCHEDULED, scheduled_date=candidate.booked_date,
            scheduled_centre=candidate.centre, assigned_to=user if not user.is_admin else candidate.assigned_to,
            priority=FollowUp.Priority.MEDIUM, created_by=user,
            notes=f"Booked via re-test call for {candidate.test.name}",
        )
    elif outcome == O.CALL_BACK:
        candidate.status = S.CONTACTED
        candidate.callback_date = callback_date or (timezone.localdate() + dt.timedelta(days=2))
    elif outcome == O.NOT_INTERESTED:
        candidate.status = S.NOT_INTERESTED
    elif outcome == O.WRONG_NUMBER:
        candidate.status = S.CLOSED
    elif outcome == O.DO_NOT_CALL:
        patient = candidate.patient
        patient.do_not_call = True
        patient.save()
        RetestCandidate.objects.open().filter(patient=patient).update(status=S.CLOSED)
        candidate.status = S.CLOSED
    # NO_ANSWER: stays in queue; attempts counter increments
    candidate.save()
    return call


def mark_conversions(visit):
    """On a return visit (any centre), convert open/booked candidates for tests repeated."""
    now = timezone.now()
    tests = {vt.test_id: vt for vt in visit.tests.all()}
    if not tests:
        return 0
    qs = RetestCandidate.objects.filter(
        patient=visit.patient, test_id__in=tests.keys(),
    ).filter(Q(status__in=RetestCandidate.OPEN_STATUSES) | Q(status=RetestCandidate.Status.NOT_INTERESTED, updated_at__gte=now - dt.timedelta(days=60)))
    n = 0
    for c in qs:
        c.status = RetestCandidate.Status.CONVERTED
        c.converted_visit = visit
        c.converted_test = tests[c.test_id]
        c.converted_at = now
        c.save()
        c.calls.filter(outcome=CallLog.Outcome.BOOKED).update(converted=True)
        n += 1
    return n
