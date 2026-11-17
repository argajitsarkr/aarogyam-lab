import json

import tablib
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Prefetch
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView

from apps.audit.models import AuditLog
from apps.audit.services import log_event
from apps.core.mixins import AdminRequiredMixin, ListPageMixin, SimpleFormPageMixin, admin_required

from . import importer
from .filters import PatientFilter
from .forms import (AddVisitTestsForm, DoctorForm, ImportUploadForm, PatientForm, TestCatalogForm, VisitDetailsForm, VisitForm,
                    VisitTestResultFormSet)
from .models import Doctor, Patient, TestCatalog, Visit, VisitTest
from .services import (active_tests, check_patient_access, check_visit_edit, create_visit, employee_centre,
                       lookup_patients, minimal_card)


# =============================================================================
# Patient list
# =============================================================================
class PatientListView(ListPageMixin):
    model = Patient
    page_key = "patients"
    url_name = "patients:list"
    template_name = "patients/list.html"
    results_template = "patients/_results.html"
    filterset_class = PatientFilter
    results_label = "patient"
    view_modes = ("table", "card")
    sort_fields = {"name": "full_name", "patient_id": "patient_id", "last_visit": "last_visit_date",
                   "created": "created_at", "locality": "locality", "visits": "visit_count"}
    default_sort = "-last_visit"
    columns = [("patient_id", "Patient ID"), ("name", "Name"), ("age_sex", "Age / Sex"), ("phone", "Phone"),
               ("locality", "Locality"), ("pin", "PIN"), ("centre", "Registered at"), ("last_visit", "Last visit"),
               ("visits", "Visits")]

    def get_base_queryset(self):
        return (
            Patient.objects.active()
            .visible_in_centres(self.request.scope.centre_ids)
            .select_related("registered_at_centre")
            .annotate(last_visit_date=Max("visits__visit_date"), visit_count=Count("visits", distinct=True))
        )


# =============================================================================
# Fast registration flow
# =============================================================================
def _tests_json():
    return json.dumps([
        {"id": t.pk, "code": t.code, "name": t.name, "price": float(t.price), "cat": t.get_category_display()}
        for t in active_tests()
    ])


@login_required
def register(request):
    """Single-screen flow: phone first → duplicate check → new patient or new visit."""
    return render(request, "patients/register.html", {"phone": request.GET.get("phone", "")})


@login_required
def lookup(request):
    """HTMX: exact phone / patient-ID match across ALL centres → minimal cards only."""
    term = request.GET.get("term", "").strip()
    matches = [minimal_card(p, request.user) for p in lookup_patients(term)]
    ctx = {"term": term, "matches": matches}
    if not matches and term:
        from apps.core.validators import PHONE_RE, normalize_phone

        phone = normalize_phone(term)
        ctx["valid_phone"] = bool(PHONE_RE.match(phone or ""))
        ctx["phone"] = phone
    return render(request, "patients/_lookup_results.html", ctx)


@login_required
def register_new(request):
    """New patient, plus a first visit unless this is a quick add.

    Quick add is for someone treated before this app existed: we know the person,
    not when they came in or what was run. Inventing a visit dated today would be a
    worse record than none, so it creates the patient only - a visit gets added from
    their page whenever the history turns up.
    """
    user = request.user
    if request.method == "POST":
        pform = PatientForm(request.POST, prefix="p")
        quick = pform.mode == PatientForm.QUICK
        vform = VisitForm(request.POST, prefix="v", user=user)
        if pform.is_valid() and (quick or vform.is_valid()):
            # Quick add has no visit form, so an Admin's centre comes from the scope
            # switcher instead. On "All Centres" there is nothing to choose from.
            requested = request.scope.centre if quick else vform.cleaned_data.get("centre")
            centre = employee_centre(user, requested)
            if centre is None:
                messages.error(request, "Pick a single centre in the scope switcher before adding a past patient.")
                return render(request, "patients/register_form.html",
                              {"pform": pform, "vform": vform, "tests_json": _tests_json(), "is_new": True})
            with transaction.atomic():
                patient = pform.save(commit=False)
                patient.registered_at_centre = centre
                patient.registered_by = user
                patient.save()
                visit = None if quick else _save_visit(vform, patient, user, centre)
            messages.success(request, f"Registered {patient.full_name} - {patient.patient_id}.")
            if visit is None:
                return redirect("patients:detail", pk=patient.pk)
            return redirect("patients:visit_detail", pk=visit.pk)
    else:
        pform = PatientForm(prefix="p", initial={"phone": request.GET.get("phone", "")})
        vform = VisitForm(prefix="v", user=user, initial={"visit_date": timezone.localdate(), "centre": request.scope.centre})
    return render(request, "patients/register_form.html",
                  {"pform": pform, "vform": vform, "tests_json": _tests_json(), "is_new": True})


def _save_visit(vform, patient, user, centre):
    fields = {k: vform.cleaned_data[k] for k in vform.Meta.fields}
    return create_visit(patient=patient, user=user, centre=centre, tests=list(vform.cleaned_data["tests"]),
                        visit_fields=fields)


@login_required
def new_visit(request, pk):
    """Add a visit for an existing patient (found via the duplicate check) at the user's centre.
    Allowed for any centre's patient — the new visit is tagged to the user's centre."""
    patient = get_object_or_404(Patient.objects.active(), pk=pk)
    user = request.user
    if request.method == "POST":
        vform = VisitForm(request.POST, prefix="v", user=user)
        if vform.is_valid():
            centre = employee_centre(user, vform.cleaned_data.get("centre"))
            visit = _save_visit(vform, patient, user, centre)
            messages.success(request, f"New visit added for {patient.full_name} at {centre.name}.")
            return redirect("patients:visit_detail", pk=visit.pk)
    else:
        vform = VisitForm(prefix="v", user=user, initial={"visit_date": timezone.localdate(), "centre": request.scope.centre})
    return render(request, "patients/register_form.html",
                  {"vform": vform, "patient": patient, "card": minimal_card(patient, user), "tests_json": _tests_json(),
                   "is_new": False})


@login_required
def localities(request):
    """HTMX datalist options for locality autocomplete (previously used values)."""
    q = request.GET.get("p-locality") or request.GET.get("locality") or request.GET.get("q", "")
    qs = Patient.objects.exclude(locality="")
    if q:
        qs = qs.filter(locality__istartswith=q.strip())
    values = qs.values_list("locality", flat=True).distinct().order_by("locality")[:15]
    return render(request, "patients/_locality_options.html", {"values": values})


# =============================================================================
# Patient record
# =============================================================================
@login_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient.objects.select_related("registered_at_centre", "registered_by"), pk=pk)
    check_patient_access(request.user, patient, request)
    visits = (
        patient.visits.active().select_related("centre", "referring_doctor", "registered_by")
        .prefetch_related(Prefetch("tests", queryset=VisitTest.objects.select_related("test")))
        .order_by("-visit_date", "-pk")
    )
    followups = patient.followups.select_related("centre", "assigned_to").order_by("-created_at")
    candidates = patient.retest_candidates.select_related("test", "centre").prefetch_related("calls__employee")
    return render(request, "patients/detail.html", {
        "patient": patient, "visits": visits, "followups": followups, "candidates": candidates,
    })


class PatientUpdateView(SimpleFormPageMixin, UpdateView):
    model = Patient
    form_class = PatientForm

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        check_patient_access(self.request.user, obj, self.request)
        return obj

    def get_success_url(self):
        return reverse("patients:detail", args=[self.object.pk])


@require_POST
@admin_required
def patient_soft_delete(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    patient.is_active = False
    patient.soft_delete(request.user)
    messages.success(request, f"{patient.full_name} archived (soft-deleted).")
    return redirect("patients:list")


# =============================================================================
# Visit detail / results
# =============================================================================
@login_required
def visit_detail(request, pk):
    visit = get_object_or_404(Visit.objects.select_related("patient", "centre", "referring_doctor", "registered_by"), pk=pk)
    check_patient_access(request.user, visit.patient, request)
    can_edit = request.user.is_admin or request.user.home_centre_id == visit.centre_id
    qs = visit.tests.select_related("test")
    # Two forms post to this page: the results grid, and "add tests", which exists
    # because registration no longer demands a test up front.
    adding = request.method == "POST" and "add_tests" in request.POST

    add_form = AddVisitTestsForm(request.POST if adding else None, visit=visit)
    if adding:
        check_visit_edit(request.user, visit)
        if add_form.is_valid():
            added = add_form.save()
            messages.success(request, f"Added {len(added)} test{'' if len(added) == 1 else 's'} to this visit.")
            return redirect("patients:visit_detail", pk=pk)

    if request.method == "POST" and not adding:
        check_visit_edit(request.user, visit)
        formset = VisitTestResultFormSet(request.POST, queryset=qs, prefix="t")
        bform = VisitDetailsForm(request.POST, instance=visit, prefix="b")
        if formset.is_valid() and bform.is_valid():
            with transaction.atomic():
                formset.save()
                bform.save()
            messages.success(request, "Visit updated.")
            return redirect("patients:visit_detail", pk=pk)
    else:
        formset = VisitTestResultFormSet(queryset=qs, prefix="t")
        bform = VisitDetailsForm(instance=visit, prefix="b")
    return render(request, "patients/visit_detail.html",
                  {"visit": visit, "formset": formset, "bform": bform, "add_form": add_form,
                   "can_edit": can_edit})


# =============================================================================
# Import (Admins only, logged)
# =============================================================================
@admin_required
def import_upload(request):
    importer.cleanup_old_imports()
    form = ImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        token, fname = importer.save_upload(form.cleaned_data["file"])
        request.session[f"import:{token}"] = {"file": fname, "centre": form.cleaned_data["centre"].pk,
                                              "name": form.cleaned_data["file"].name}
        return redirect("patients:import_map", token=token)
    return render(request, "patients/import_upload.html", {"form": form, "fields": importer.TARGET_FIELDS})


def _import_state(request, token):
    state = request.session.get(f"import:{token}")
    if not state:
        raise Http404("Import session expired — please upload again.")
    return state


@admin_required
def import_map(request, token):
    state = _import_state(request, token)
    dataset = importer.load_dataset(state["file"])
    headers = [h for h in dataset.headers if h]
    if request.method == "POST":
        mapping = {f: request.POST.get(f) for f, *_ in importer.TARGET_FIELDS if request.POST.get(f) in headers}
        missing = [label for f, label, req in importer.TARGET_FIELDS if req and f not in mapping]
        if missing:
            messages.error(request, f"Please map required columns: {', '.join(missing)}")
        else:
            state["mapping"] = mapping
            request.session[f"import:{token}"] = state
            return redirect("patients:import_preview", token=token)
    mapping = state.get("mapping") or importer.guess_mapping(headers)
    return render(request, "patients/import_map.html", {
        "token": token, "headers": headers, "fields": importer.TARGET_FIELDS, "mapping": mapping,
        "sample": list(dataset)[:3], "row_count": len(dataset), "state": state,
    })


@admin_required
def import_preview(request, token):
    from apps.centres.models import Centre

    state = _import_state(request, token)
    if "mapping" not in state:
        return redirect("patients:import_map", token=token)
    centre = get_object_or_404(Centre, pk=state["centre"])
    rows = importer.validate_rows(importer.load_dataset(state["file"]), state["mapping"], centre)
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("ok", "duplicate", "error")}
    if request.method == "POST":
        created = importer.commit_rows(rows, request.user)
        log_event(AuditLog.Action.IMPORT, user=request.user, centre_id=centre.pk,
                  note=f"Imported {created} patients from {state['name']} (skipped {counts['duplicate']} duplicates, {counts['error']} errors)")
        del request.session[f"import:{token}"]
        messages.success(request, f"Imported {created} patients. Skipped {counts['duplicate']} duplicates and {counts['error']} rows with errors.")
        return redirect("patients:list")
    show = request.GET.get("show", "all")
    shown = rows if show == "all" else [r for r in rows if r["status"] == show]
    return render(request, "patients/import_preview.html", {
        "token": token, "rows": shown[:200], "counts": counts, "total": len(rows), "centre": centre, "show": show,
    })


# =============================================================================
# Doctors & test catalogue
# =============================================================================
class DoctorListView(ListPageMixin):
    model = Doctor
    page_key = "doctors"
    url_name = "patients:doctors"
    template_name = "patients/doctors.html"
    results_template = "patients/_doctors_results.html"
    sort_fields = {"name": "name", "clinic": "clinic", "referrals": "referral_count"}
    default_sort = "name"
    columns = [("name", "Name"), ("clinic", "Clinic"), ("specialty", "Specialty"), ("phone", "Phone"),
               ("locality", "Locality"), ("referrals", "Referrals")]

    def get_base_queryset(self):
        from django.db.models import Q

        qs = Doctor.objects.annotate(referral_count=Count("visits", filter=Q(visits__centre_id__in=self.request.scope.centre_ids)))
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(clinic__icontains=q) | Q(locality__icontains=q))
        return qs


class DoctorCreateView(SimpleFormPageMixin, CreateView):
    model = Doctor
    form_class = DoctorForm
    page_heading = "New doctor"
    success_url = reverse_lazy("patients:doctors")


class DoctorUpdateView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    model = Doctor
    form_class = DoctorForm
    success_url = reverse_lazy("patients:doctors")


class TestListView(ListPageMixin):
    model = TestCatalog
    page_key = "tests"
    url_name = "patients:tests"
    template_name = "patients/tests.html"
    results_template = "patients/_tests_results.html"
    sort_fields = {"name": "name", "code": "code", "price": "price", "category": "category", "interval": "retest_interval_days"}
    default_sort = "name"
    paginate_by = 100
    columns = [("code", "Code"), ("name", "Name"), ("category", "Category"), ("sample", "Sample"),
               ("price", "Price"), ("interval", "Re-test interval"), ("chronic", "Chronic")]

    def get_base_queryset(self):
        from django.db.models import Q

        qs = TestCatalog.objects.all()
        if not self.request.user.is_admin:
            qs = qs.filter(is_active=True)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        cat = self.request.GET.get("category")
        if cat:
            qs = qs.filter(category=cat)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = TestCatalog.Category.choices
        return ctx


class TestCreateView(AdminRequiredMixin, SimpleFormPageMixin, CreateView):
    model = TestCatalog
    form_class = TestCatalogForm
    page_heading = "New test"
    success_url = reverse_lazy("patients:tests")


class TestUpdateView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    model = TestCatalog
    form_class = TestCatalogForm
    success_url = reverse_lazy("patients:tests")


@login_required
def tests_json(request):
    return JsonResponse(json.loads(_tests_json()), safe=False)

