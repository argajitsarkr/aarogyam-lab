import datetime as dt
from decimal import Decimal

import django_filters
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.centres.models import Centre
from apps.core.calendar_utils import CAL_MODES, build_calendar, date_range_for, parse_anchor
from apps.core.filters import StyledFilterSet
from apps.core.mixins import ListPageMixin, admin_required
from apps.core.preferences import get_pref, set_pref
from apps.patients.models import TestCatalog, VisitTest

from .forms import CallOutcomeForm, ReassignForm
from .models import CallLog, RetestCandidate
from .services import generate_candidates, log_call


def _check_access(user, cand):
    if user.is_admin or cand.centre_id == user.home_centre_id:
        return
    raise PermissionDenied("This call belongs to another centre.")


# =============================================================================
# My Call List
# =============================================================================
@login_required
def my_calls(request):
    today = timezone.localdate()
    qs = (RetestCandidate.objects.open().for_scope(request.scope)
          .select_related("patient", "test", "centre", "source_test", "assigned_to")
          .filter(patient__do_not_call=False))
    show_all = request.user.is_admin or request.GET.get("all")
    if not show_all:
        qs = qs.filter(assigned_to=request.user)
    # Scheduled ones are waiting for the patient to come in — show them separately.
    to_call = qs.exclude(status=RetestCandidate.Status.SCHEDULED).filter(
        Q(callback_date__isnull=True) | Q(callback_date__lte=today))
    later = qs.filter(status=RetestCandidate.Status.CONTACTED, callback_date__gt=today).order_by("callback_date")[:50]
    booked = qs.filter(status=RetestCandidate.Status.SCHEDULED).order_by("booked_date")[:50]
    callbacks_due = to_call.filter(callback_date__isnull=False).order_by("callback_date", "-priority_score")
    fresh = to_call.filter(callback_date__isnull=True).order_by("-priority_score", "due_date")
    calls_today = CallLog.objects.filter(employee=request.user, called_at__date=today).count()
    return render(request, "retest/my_calls.html", {
        "callbacks_due": callbacks_due[:100], "fresh": fresh[:200], "later": later, "booked": booked,
        "show_all": show_all, "calls_today": calls_today, "today": today,
        "tomorrow": today + dt.timedelta(days=1), "in_two_days": today + dt.timedelta(days=2),
    })


@require_POST
@login_required
def log_outcome(request, pk):
    cand = get_object_or_404(RetestCandidate.objects.select_related("patient", "test", "centre", "source_test"), pk=pk)
    _check_access(request.user, cand)
    form = CallOutcomeForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("; ".join(e for errs in form.errors.values() for e in errs))
    d = form.cleaned_data
    callback = d["callback_date"] if d["outcome"] == CallLog.Outcome.CALL_BACK else None
    booked = d["booked_date"] if d["outcome"] == CallLog.Outcome.BOOKED else None
    log_call(cand, request.user, d["outcome"], d["notes"], callback, booked)
    if request.headers.get("HX-Request"):
        cand.refresh_from_db()
        return render(request, "retest/_call_row_done.html", {"c": cand, "outcome": CallLog.Outcome(d["outcome"]).label})
    messages.success(request, "Call logged.")
    return redirect(request.POST.get("next") or "retest:my_calls")


# =============================================================================
# Queue (table / card / kanban / calendar)
# =============================================================================
class CandidateFilter(StyledFilterSet):
    q = django_filters.CharFilter(method="search", label="Patient",
                                  widget=forms.TextInput(attrs={"type": "search", "placeholder": "Name, phone, ID…"}))
    centre = django_filters.ModelChoiceFilter(queryset=Centre.objects.filter(is_active=True), empty_label="Any centre")
    assigned_to = django_filters.ModelChoiceFilter(queryset=User.objects.none(), label="Employee", empty_label="Anyone")
    test = django_filters.ModelChoiceFilter(queryset=TestCatalog.objects.filter(retest_interval_days__isnull=False), empty_label="Any test")
    flag = django_filters.ChoiceFilter(field_name="source_test__flag", choices=VisitTest.Flag.choices, empty_label="Any flag")
    status = django_filters.ChoiceFilter(choices=RetestCandidate.Status.choices, empty_label="Open (default)", method="by_status")

    class Meta:
        model = RetestCandidate
        fields = ["q", "centre", "assigned_to", "test", "flag", "status"]

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, request=request, **kwargs)
        staff = User.objects.active_employees()
        if request and not request.user.is_admin:
            self.filters.pop("centre")
            self.form.fields.pop("centre", None)
            staff = staff.filter(home_centre=request.user.home_centre)
        self.form.fields["assigned_to"].queryset = staff
        self.filters["assigned_to"].queryset = staff

    def search(self, qs, name, value):
        return qs.filter(Q(patient__full_name__icontains=value) | Q(patient__phone__startswith=value)
                         | Q(patient__patient_id__icontains=value))

    def by_status(self, qs, name, value):
        return qs.filter(status=value)


class CandidateListView(ListPageMixin):
    model = RetestCandidate
    page_key = "retest"
    url_name = "retest:list"
    template_name = "retest/list.html"
    results_template = "retest/_results.html"
    filterset_class = CandidateFilter
    view_modes = ("table", "card", "kanban", "calendar")
    sort_fields = {"priority": "priority_score", "due": "due_date", "patient": "patient__full_name",
                   "test": "test__name", "attempts": "attempts"}
    default_sort = "-priority"
    columns = [("patient", "Patient"), ("test", "Test"), ("flag", "Last flag"), ("due", "Due"),
               ("priority", "Priority"), ("centre", "Centre"), ("assigned", "Assigned"), ("status", "Status"),
               ("attempts", "Attempts")]

    def get_base_queryset(self):
        qs = (RetestCandidate.objects.for_scope(self.request.scope)
              .select_related("patient", "test", "centre", "assigned_to", "source_test"))
        mode = self.get_view_mode()
        if mode == "kanban":
            recent = timezone.now() - dt.timedelta(days=30)
            return qs.filter(Q(status__in=RetestCandidate.OPEN_STATUSES) | Q(status=RetestCandidate.Status.CONVERTED, converted_at__gte=recent))
        if not self.request.GET.get("status"):
            qs = qs.open()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mode = self.get_view_mode()
        if mode == "kanban":
            items = list(ctx["object_list"])
            ctx["kanban"] = [(s, RetestCandidate.Status(s).label, [i for i in items if i.status == s]) for s in RetestCandidate.KANBAN_COLUMNS]
        elif mode == "calendar":
            cal_mode = self.request.GET.get("cal") or get_pref(self.request.user, "cal:retest", "month")
            cal_mode = cal_mode if cal_mode in CAL_MODES else "month"
            set_pref(self.request.user, "cal:retest", cal_mode)
            anchor = parse_anchor(self.request.GET.get("d"))
            start, end = date_range_for(cal_mode, anchor)
            items = [i for i in ctx["object_list"] if start <= i.calendar_date <= end]
            ctx["cal"] = build_calendar(cal_mode, anchor, items, "calendar_date")
        return ctx


@require_POST
@login_required
def candidate_move(request, pk):
    cand = get_object_or_404(RetestCandidate, pk=pk)
    _check_access(request.user, cand)
    status = request.POST.get("status")
    if status not in RetestCandidate.KANBAN_COLUMNS:
        return HttpResponseBadRequest("Invalid status")
    cand.status = status
    if status == RetestCandidate.Status.SCHEDULED and not cand.booked_date:
        cand.booked_date = max(cand.due_date, timezone.localdate())
    if status == RetestCandidate.Status.CONVERTED and not cand.converted_at:
        cand.converted_at = timezone.now()
    cand.save()
    return HttpResponse(status=204)


@require_POST
@admin_required
def candidate_reassign(request, pk):
    cand = get_object_or_404(RetestCandidate, pk=pk)
    form = ReassignForm(request.POST, centre=cand.centre)
    if form.is_valid():
        cand.assigned_to = form.cleaned_data["assigned_to"]
        cand.save(update_fields=["assigned_to", "updated_at"])
        messages.success(request, f"Reassigned to {cand.assigned_to}.")
    else:
        messages.error(request, "Choose an employee of the same centre.")
    return redirect(request.POST.get("next") or "retest:list")


@require_POST
@admin_required
def run_generator(request):
    n = generate_candidates()
    messages.success(request, f"Re-test scan complete: {n} new candidate{'s' if n != 1 else ''}.")
    return redirect("retest:list")


# =============================================================================
# Analytics (Admins)
# =============================================================================
@admin_required
def analytics(request):
    today = timezone.localdate()
    try:
        start = dt.date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        start = today - dt.timedelta(days=30)
    try:
        end = dt.date.fromisoformat(request.GET.get("to", ""))
    except ValueError:
        end = today
    centre_ids = request.scope.centre_ids
    calls = CallLog.objects.filter(called_at__date__gte=start, called_at__date__lte=end, centre_id__in=centre_ids)
    contacted_q = Q(outcome__in=CallLog.CONTACTED_OUTCOMES)
    booked_q = Q(outcome=CallLog.Outcome.BOOKED)

    def rate(b, c):
        return round(100 * b / c, 1) if c else 0

    conv = (RetestCandidate.objects.filter(status=RetestCandidate.Status.CONVERTED, converted_at__date__gte=start,
                                           converted_at__date__lte=end, centre_id__in=centre_ids, calls__isnull=False)
            .distinct())
    per_emp = []
    for row in (calls.values("employee", "employee__first_name", "employee__username", "centre__short_code")
                .annotate(total=Count("id"), contacted=Count("id", filter=contacted_q), booked=Count("id", filter=booked_q))
                .order_by("-booked")):
        emp_conv = conv.filter(calls__employee=row["employee"], calls__outcome=CallLog.Outcome.BOOKED)
        revenue = emp_conv.aggregate(r=Sum("converted_test__price_charged"))["r"] or Decimal(0)
        per_emp.append({**row, "rate": rate(row["booked"], row["contacted"]), "converted": emp_conv.count(), "revenue": revenue})

    per_centre = []
    for c in Centre.objects.filter(pk__in=centre_ids):
        cc = calls.filter(centre=c)
        agg = cc.aggregate(total=Count("id"), contacted=Count("id", filter=contacted_q), booked=Count("id", filter=booked_q))
        cconv = conv.filter(centre=c)
        per_centre.append({"centre": c, **agg, "rate": rate(agg["booked"], agg["contacted"]), "converted": cconv.count(),
                           "revenue": cconv.aggregate(r=Sum("converted_test__price_charged"))["r"] or Decimal(0)})

    # Weekly trend (12 weeks)
    weeks, booked_series, conv_series, rate_series = [], [], [], []
    wk_start = today - dt.timedelta(days=today.weekday() + 7 * 11)
    all_calls = CallLog.objects.filter(centre_id__in=centre_ids)
    for i in range(12):
        ws, we = wk_start + dt.timedelta(days=7 * i), wk_start + dt.timedelta(days=7 * i + 6)
        wc = all_calls.filter(called_at__date__gte=ws, called_at__date__lte=we).aggregate(
            contacted=Count("id", filter=contacted_q), booked=Count("id", filter=booked_q))
        weeks.append(ws.strftime("%d-%m"))
        booked_series.append(wc["booked"])
        rate_series.append(rate(wc["booked"], wc["contacted"]))
        conv_series.append(RetestCandidate.objects.filter(centre_id__in=centre_ids, status="CONVERTED",
                                                          converted_at__date__gte=ws, converted_at__date__lte=we).count())
    totals = calls.aggregate(total=Count("id"), contacted=Count("id", filter=contacted_q), booked=Count("id", filter=booked_q))
    return render(request, "retest/analytics.html", {
        "start": start, "end": end, "per_emp": per_emp, "per_centre": per_centre, "totals": totals,
        "total_rate": rate(totals["booked"], totals["contacted"]), "total_converted": conv.count(),
        "total_revenue": conv.aggregate(r=Sum("converted_test__price_charged"))["r"] or Decimal(0),
        "trend": {"labels": weeks, "booked": booked_series, "converted": conv_series, "rate": rate_series},
        "open_count": RetestCandidate.objects.open().filter(centre_id__in=centre_ids).count(),
    })
