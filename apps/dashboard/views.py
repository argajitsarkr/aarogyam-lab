import datetime as dt

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.centres.models import Centre
from apps.core.mixins import admin_required
from apps.followups.models import FollowUp
from apps.patients.models import Patient
from apps.retest.models import RetestCandidate

from . import services


def _date_range(request, default_days=30):
    today = timezone.localdate()
    try:
        start = dt.date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        start = today - dt.timedelta(days=default_days - 1)
    try:
        end = dt.date.fromisoformat(request.GET.get("to", ""))
    except ValueError:
        end = today
    return start, end


@login_required
def home(request):
    centre_ids = request.scope.centre_ids
    user = request.user
    ctx = {"kpi": services.kpis(centre_ids, user), "charts": services.chart_data(centre_ids)}
    my_calls = (RetestCandidate.objects.open().filter(centre_id__in=centre_ids, patient__do_not_call=False)
                .exclude(status=RetestCandidate.Status.SCHEDULED).select_related("patient", "test"))
    my_fu = FollowUp.objects.open().filter(centre_id__in=centre_ids, due_date__lte=timezone.localdate()).select_related("patient")
    if not user.is_admin:
        my_calls = my_calls.filter(assigned_to=user)
        my_fu = my_fu.filter(Q(assigned_to=user) | Q(assigned_to__isnull=True))
    ctx["my_calls"] = my_calls.order_by("-priority_score", "due_date")[:8]
    ctx["my_followups"] = my_fu.order_by("due_date", "priority")[:8]
    if user.is_admin:
        start, end = _date_range(request)
        ctx.update(start=start, end=end, comparison=services.centre_comparison(centre_ids, start, end))
    return render(request, "dashboard/home.html", ctx)


@admin_required
def compare(request):
    start, end = _date_range(request)
    ids = list(Centre.objects.filter(is_active=True).values_list("pk", flat=True))
    return render(request, "dashboard/compare.html", {
        "start": start, "end": end, "comparison": services.centre_comparison(ids, start, end),
        "charts": services.chart_data(ids, days=max(7, min((end - start).days + 1, 90))),
    })


@admin_required
def map_view(request):
    """Centres + aggregated patient density by PIN code. No individual patient data."""
    centre_ids = request.scope.centre_ids
    mapped, unmapped = services.density_by_pin(centre_ids)
    centres = [{"name": c.name, "code": c.short_code, "color": c.colour, "lat": float(c.latitude), "lng": float(c.longitude),
                "patients": c.n}
               for c in Centre.objects.filter(pk__in=centre_ids, latitude__isnull=False, longitude__isnull=False)
               .annotate(n=Count("patients_registered"))]
    localities = (Patient.objects.active().visible_in_centres(centre_ids).exclude(locality="")
                  .values("locality").annotate(n=Count("id")).order_by("-n")[:25])
    return render(request, "dashboard/map.html", {
        "map_data": {"centres": centres, "pins": mapped}, "unmapped": unmapped[:50], "localities": localities,
        "centres_without_coords": Centre.objects.filter(pk__in=centre_ids, latitude__isnull=True),
    })
