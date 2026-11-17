import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.calendar_utils import CAL_MODES, build_calendar, date_range_for, parse_anchor
from apps.core.assignment import pick_assignee
from apps.core.mixins import ListPageMixin
from apps.core.preferences import get_pref, set_pref
from apps.patients.models import Patient
from apps.patients.services import check_patient_access

from .filters import FollowUpFilter
from .forms import FollowUpForm, StatusUpdateForm
from .models import FollowUp
from .services import change_status

TABS = [("due_today", "Due today"), ("overdue", "Overdue"), ("upcoming", "Upcoming (7 days)"),
        ("open", "All open"), ("completed", "Completed"), ("all", "Everything")]


def _check_fu_access(user, fu):
    if user.is_admin or fu.centre_id in user.accessible_centre_ids():
        return
    raise PermissionDenied("This follow-up belongs to another centre.")


class FollowUpListView(ListPageMixin):
    model = FollowUp
    page_key = "followups"
    url_name = "followups:list"
    template_name = "followups/list.html"
    results_template = "followups/_results.html"
    filterset_class = FollowUpFilter
    view_modes = ("table", "card", "kanban", "calendar")
    sort_fields = {"due": "due_date", "priority": "priority", "patient": "patient__full_name", "status": "status",
                   "created": "created_at"}
    default_sort = "due"
    columns = [("patient", "Patient"), ("centre", "Centre"), ("reason", "Reason"), ("due", "Due"),
               ("priority", "Priority"), ("assigned", "Assigned to"), ("status", "Status"), ("next", "Next action")]

    def get_tab(self):
        tab = self.request.GET.get("tab")
        return tab if tab in dict(TABS) else ("open" if self.get_view_mode() in ("kanban", "calendar") else "due_today")

    def get_base_queryset(self):
        qs = (FollowUp.objects.for_scope(self.request.scope)
              .select_related("patient", "centre", "assigned_to", "referring_doctor", "source_test__test"))
        if self.request.GET.get("mine"):
            qs = qs.filter(assigned_to=self.request.user)
        mode = self.get_view_mode()
        today = timezone.localdate()
        if mode == "kanban":
            recent = today - dt.timedelta(days=30)
            return qs.filter(status__in=FollowUp.OPEN_STATUSES) | qs.filter(status=FollowUp.Status.COMPLETED, completed_at__date__gte=recent)
        if mode == "calendar":
            return qs
        tab = self.get_tab()
        return {
            "due_today": qs.due_today(), "overdue": qs.overdue(), "upcoming": qs.upcoming(7), "open": qs.open(),
            "completed": qs.filter(status=FollowUp.Status.COMPLETED), "all": qs,
        }[tab]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = FollowUp.objects.for_scope(self.request.scope)
        ctx["tabs"] = TABS
        ctx["tab"] = self.get_tab()
        ctx["tab_counts"] = {"due_today": qs.due_today().count(), "overdue": qs.overdue().count(),
                             "upcoming": qs.upcoming(7).count()}
        mode = self.get_view_mode()
        items = list(ctx["object_list"]) if mode in ("kanban", "calendar") else None
        if mode == "kanban":
            ctx["kanban"] = [(s, FollowUp.Status(s).label, [i for i in items if i.status == s]) for s in FollowUp.KANBAN_COLUMNS]
        elif mode == "calendar":
            cal_mode = self.request.GET.get("cal") or get_pref(self.request.user, "cal:followups", "month")
            if cal_mode not in CAL_MODES:
                cal_mode = "month"
            set_pref(self.request.user, "cal:followups", cal_mode)
            anchor = parse_anchor(self.request.GET.get("d"))
            start, end = date_range_for(cal_mode, anchor)
            visible = [i for i in items if i.calendar_date and start <= i.calendar_date <= end]
            ctx["cal"] = build_calendar(cal_mode, anchor, visible, "calendar_date")
        return ctx


@login_required
def followup_create(request):
    patient = get_object_or_404(Patient.objects.active(), pk=request.GET.get("patient") or request.POST.get("patient"))
    check_patient_access(request.user, patient, request)
    user = request.user
    centre = user.home_centre if not user.is_admin else (request.scope.centre or (patient.last_visit.centre if patient.last_visit else patient.registered_at_centre))
    visit = patient.last_visit
    form = FollowUpForm(request.POST or None, centre=centre,
                        initial={"due_date": timezone.localdate() + dt.timedelta(days=7),
                                 "referring_doctor": visit.referring_doctor if visit else None})
    if request.method == "POST" and form.is_valid():
        fu = form.save(commit=False)
        fu.patient, fu.centre, fu.created_by, fu.source_visit = patient, centre, user, visit
        if not fu.assigned_to:
            fu.assigned_to = pick_assignee(centre, "assigned_followups", FollowUp.OPEN_STATUSES)
        fu.save()
        messages.success(request, "Follow-up created.")
        return redirect("followups:detail", pk=fu.pk)
    return render(request, "followups/form.html", {"form": form, "patient": patient, "centre": centre})


@login_required
def followup_detail(request, pk):
    fu = get_object_or_404(FollowUp.objects.select_related("patient", "centre", "assigned_to", "source_test__test",
                                                           "completed_visit", "scheduled_centre"), pk=pk)
    _check_fu_access(request.user, fu)
    if request.method == "POST":
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            change_status(fu, request.user, d["status"], d["note"], d["scheduled_date"], d["scheduled_centre"],
                          d["next_action_date"])
            messages.success(request, "Follow-up updated.")
            return redirect("followups:detail", pk=pk)
    else:
        form = StatusUpdateForm(initial={"status": fu.status, "scheduled_date": fu.scheduled_date,
                                         "scheduled_centre": fu.scheduled_centre or fu.centre,
                                         "next_action_date": fu.next_action_date})
    edit_form = FollowUpForm(instance=fu, centre=fu.centre)
    return render(request, "followups/detail.html",
                  {"fu": fu, "form": form, "edit_form": edit_form, "notes": fu.contact_notes.select_related("user")})


@require_POST
@login_required
def followup_edit(request, pk):
    fu = get_object_or_404(FollowUp, pk=pk)
    _check_fu_access(request.user, fu)
    form = FollowUpForm(request.POST, instance=fu, centre=fu.centre)
    if form.is_valid():
        form.save()
        messages.success(request, "Details saved.")
    else:
        messages.error(request, "Could not save: " + "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("followups:detail", pk=pk)


@require_POST
@login_required
def followup_move(request, pk):
    """Kanban drag-and-drop (HTMX)."""
    fu = get_object_or_404(FollowUp, pk=pk)
    _check_fu_access(request.user, fu)
    status = request.POST.get("status")
    if status not in FollowUp.KANBAN_COLUMNS:
        return HttpResponseBadRequest("Invalid status")
    sched = None
    if status == FollowUp.Status.SCHEDULED and not fu.scheduled_date:
        sched = max(fu.due_date, timezone.localdate())
    change_status(fu, request.user, status, "Moved on Kanban board", scheduled_date=sched)
    return HttpResponse(status=204)
