import datetime as dt
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.centres.models import Centre
from apps.followups.models import FollowUp
from apps.patients.models import Patient, Visit, VisitTest
from apps.retest.models import CallLog, RetestCandidate


def _net(qs):
    agg = qs.aggregate(t=Sum("total_amount"), d=Sum("discount"), p=Sum("amount_paid"))
    return (agg["t"] or Decimal(0)) - (agg["d"] or Decimal(0)), agg["p"] or Decimal(0)


def kpis(centre_ids, user):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    visits_today = Visit.objects.active().filter(centre_id__in=centre_ids, visit_date=today)
    billed, collected = _net(visits_today)
    fu = FollowUp.objects.filter(centre_id__in=centre_ids)
    data = {
        "registrations_today": Patient.objects.filter(registered_at_centre_id__in=centre_ids, created_at__date=today).count(),
        "visits_today": visits_today.count(),
        "revenue_today": billed,
        "collected_today": collected,
        "followups_due": fu.due_today().count(),
        "followups_overdue": fu.overdue().count(),
        "retest_pending": RetestCandidate.objects.open().filter(centre_id__in=centre_ids).count(),
        "my_calls_today": CallLog.objects.filter(employee=user, called_at__date=today).count(),
        "my_conversions_month": RetestCandidate.objects.filter(
            status=RetestCandidate.Status.CONVERTED, converted_at__date__gte=month_start,
            calls__employee=user, calls__outcome=CallLog.Outcome.BOOKED).distinct().count(),
    }
    return data


def centre_comparison(centre_ids, start, end):
    rows = []
    for c in Centre.objects.filter(pk__in=centre_ids).order_by("-is_head_centre", "name"):
        visits = Visit.objects.active().filter(centre=c, visit_date__gte=start, visit_date__lte=end)
        billed, collected = _net(visits)
        calls = CallLog.objects.filter(centre=c, called_at__date__gte=start, called_at__date__lte=end)
        contacted = calls.filter(outcome__in=CallLog.CONTACTED_OUTCOMES).count()
        booked = calls.filter(outcome=CallLog.Outcome.BOOKED).count()
        fu = FollowUp.objects.filter(centre=c, due_date__gte=start, due_date__lte=end)
        fu_total = fu.count()
        fu_done = fu.filter(status=FollowUp.Status.COMPLETED).count()
        rows.append({
            "centre": c,
            "visits": visits.count(),
            "revenue": billed,
            "collected": collected,
            "new_patients": Patient.objects.filter(registered_at_centre=c, created_at__date__gte=start, created_at__date__lte=end).count(),
            "retest_rate": round(100 * booked / contacted, 1) if contacted else 0,
            "followup_rate": round(100 * fu_done / fu_total, 1) if fu_total else 0,
            "fu_total": fu_total,
        })
    return rows


def chart_data(centre_ids, days=30):
    today = timezone.localdate()
    start = today - dt.timedelta(days=days - 1)
    labels = [(start + dt.timedelta(days=i)) for i in range(days)]
    centres = list(Centre.objects.filter(pk__in=centre_ids).order_by("-is_head_centre", "name"))

    visit_counts = {(r["centre_id"], r["visit_date"]): r["n"] for r in
                    Visit.objects.active().filter(centre_id__in=centre_ids, visit_date__gte=start)
                    .values("centre_id", "visit_date").annotate(n=Count("id"))}
    reg_counts = {(r["registered_at_centre_id"], r["d"]): r["n"] for r in
                  Patient.objects.filter(registered_at_centre_id__in=centre_ids, created_at__date__gte=start)
                  .annotate(d=TruncDate("created_at")).values("registered_at_centre_id", "d").annotate(n=Count("id"))}

    def series(counts):
        return [{"label": c.short_code, "color": c.colour, "data": [counts.get((c.pk, d), 0) for d in labels]} for c in centres]

    top_tests = {}
    for c in centres:
        top_tests[c.short_code] = list(
            VisitTest.objects.filter(visit__centre=c, visit__visit_date__gte=start - dt.timedelta(days=60))
            .values(name=F("test__name")).annotate(n=Count("id")).order_by("-n")[:10])
    localities = {}
    for c in centres:
        localities[c.short_code] = list(
            Patient.objects.filter(Q(registered_at_centre=c) | Q(visits__centre=c)).exclude(locality="")
            .values("locality").annotate(n=Count("id", distinct=True)).order_by("-n")[:10])

    # Re-test conversion trend: weekly (12 weeks)
    wk_start = today - dt.timedelta(days=today.weekday() + 7 * 11)
    weeks = [wk_start + dt.timedelta(days=7 * i) for i in range(12)]
    trend = []
    calls = CallLog.objects.filter(centre_id__in=centre_ids)
    for w in weeks:
        r = calls.filter(called_at__date__gte=w, called_at__date__lte=w + dt.timedelta(days=6)).aggregate(
            contacted=Count("id", filter=Q(outcome__in=CallLog.CONTACTED_OUTCOMES)),
            booked=Count("id", filter=Q(outcome=CallLog.Outcome.BOOKED)))
        trend.append(round(100 * r["booked"] / r["contacted"], 1) if r["contacted"] else 0)

    return {
        "labels": [d.strftime("%d-%m") for d in labels],
        "visits": series(visit_counts),
        "registrations": series(reg_counts),
        "top_tests": top_tests,
        "localities": localities,
        "conversion": {"labels": [w.strftime("%d-%m") for w in weeks], "data": trend},
    }


def density_by_pin(centre_ids):
    """Aggregated patient counts per PIN code — no names or addresses."""
    from apps.patients.models import PinCodeLocation

    counts = (Patient.objects.active().visible_in_centres(centre_ids).exclude(pin_code="")
              .values("pin_code").annotate(n=Count("id")).order_by("-n"))
    locs = {p.pin_code: p for p in PinCodeLocation.objects.all()}
    mapped, unmapped = [], []
    for r in counts:
        loc = locs.get(r["pin_code"])
        if loc:
            mapped.append({"pin": r["pin_code"], "n": r["n"], "lat": float(loc.latitude), "lng": float(loc.longitude), "label": loc.label})
        else:
            unmapped.append({"pin": r["pin_code"], "n": r["n"]})
    return mapped, unmapped
