import datetime as dt
from decimal import Decimal, InvalidOperation

import tablib
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.audit.models import AuditLog
from apps.audit.services import log_event
from apps.core.forms import StyledFormMixin
from apps.core.mixins import AdminRequiredMixin, SimpleFormPageMixin, admin_required
from apps.patients.models import TestCatalog

from .models import Competitor, CompetitorPrice
from .services import build_matrix, package_totals


@login_required
def compare(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    competitors, rows = build_matrix(q=q or None, category=category or None)
    tpl = "pricing/_matrix.html" if request.headers.get("HX-Request") else "pricing/compare.html"
    return render(request, tpl, {"competitors": competitors, "rows": rows, "q": q, "category": category,
                                 "categories": TestCatalog.Category.choices})


@login_required
def lookup(request):
    """Front-desk single-test card: large font, tablet / print friendly."""
    test_id = request.GET.get("test")
    ctx = {"tests": TestCatalog.objects.filter(is_active=True).only("id", "name", "code").order_by("name")}
    if test_id:
        competitors, rows = build_matrix(test_ids=[test_id])
        if rows:
            ctx.update(row=rows[0], competitors=competitors,
                       pairs=[(c, cell) for c, cell in zip(competitors, rows[0]["cells"])])
    return render(request, "pricing/lookup.html", ctx)


@login_required
def package(request):
    ids = [i for i in request.GET.getlist("tests") if i.isdigit()]
    ctx = {"tests": TestCatalog.objects.filter(is_active=True).only("id", "name", "code", "price").order_by("name"),
           "selected": set(int(i) for i in ids)}
    if ids:
        competitors, rows = build_matrix(test_ids=ids)
        ctx.update(rows=rows, competitors=competitors, totals=package_totals(competitors, rows))
    return render(request, "pricing/package.html", ctx)


# =============================================================================
# Admin: price management
# =============================================================================
class PriceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CompetitorPrice
        fields = ["test", "competitor", "price", "source_note", "last_verified_on"]
        widgets = {"last_verified_on": forms.DateInput()}


@admin_required
def manage(request):
    """Grid editor: one row per test, one input per competitor. Admin only."""
    q = request.GET.get("q", "").strip()
    competitors, rows = build_matrix(q=q or None)
    rows = rows[:100] if not q else rows
    return render(request, "pricing/manage.html", {"competitors": competitors, "rows": rows, "q": q,
                                                   "today": timezone.localdate(),
                                                   "sources": CompetitorPrice.Source.choices})


@require_POST
@admin_required
def save_grid(request):
    """Save edited cells: inputs named price_<test>_<competitor>."""
    source = request.POST.get("source_note", "")[:120]
    try:
        verified = dt.date.fromisoformat(request.POST.get("verified_on", ""))
    except ValueError:
        verified = timezone.localdate()
    changed = 0
    with transaction.atomic():
        for key, val in request.POST.items():
            if not key.startswith("price_"):
                continue
            try:
                _, test_id, comp_id = key.split("_")
                test_id, comp_id = int(test_id), int(comp_id)
            except ValueError:
                continue
            val = val.strip()
            original = request.POST.get(f"orig_{test_id}_{comp_id}", "").strip()
            if val == original:
                continue
            if val == "":
                CompetitorPrice.objects.filter(test_id=test_id, competitor_id=comp_id).delete()
                changed += 1
                continue
            try:
                price = Decimal(val)
                if price < 0:
                    raise InvalidOperation
            except InvalidOperation:
                messages.error(request, f"Ignored invalid price '{val}'.")
                continue
            CompetitorPrice.objects.update_or_create(
                test_id=test_id, competitor_id=comp_id,
                defaults={"price": price, "source_note": source, "last_verified_on": verified, "entered_by": request.user},
            )
            changed += 1
    messages.success(request, f"Saved {changed} price change{'s' if changed != 1 else ''}.")
    return redirect(request.POST.get("next") or "pricing:manage")


@require_POST
@admin_required
def mark_verified(request, test_id):
    n = CompetitorPrice.objects.filter(test_id=test_id).update(last_verified_on=timezone.localdate(), entered_by=request.user)
    messages.success(request, f"Marked {n} prices as verified today.")
    return redirect(request.POST.get("next") or "pricing:manage")


@admin_required
def bulk_upload(request):
    """Excel/CSV columns: test_code, competitor, price, source, last_verified_on (DD-MM-YYYY)."""
    report = None
    if request.method == "POST" and request.FILES.get("file"):
        f = request.FILES["file"]
        try:
            if f.name.lower().endswith(".xlsx"):
                ds = tablib.Dataset().load(f.read(), format="xlsx")
            else:
                ds = tablib.Dataset().load(f.read().decode("utf-8-sig"), format="csv")
        except Exception as exc:  # noqa: BLE001 — show any parse error to the admin
            messages.error(request, f"Could not read file: {exc}")
            return redirect("pricing:bulk_upload")
        headers = [str(h or "").strip().lower().replace(" ", "_") for h in ds.headers]
        tests = {t.code.upper(): t for t in TestCatalog.objects.all()}
        comps = {c.name.lower(): c for c in Competitor.objects.all()}
        ok, errors = 0, []
        with transaction.atomic():
            for n, raw in enumerate(ds, start=2):
                r = dict(zip(headers, raw))
                test = tests.get(str(r.get("test_code") or "").strip().upper())
                comp = comps.get(str(r.get("competitor") or "").strip().lower())
                if not test or not comp:
                    errors.append(f"Row {n}: unknown test code or competitor")
                    continue
                try:
                    price = Decimal(str(r.get("price")).strip())
                except (InvalidOperation, TypeError):
                    errors.append(f"Row {n}: invalid price")
                    continue
                verified = r.get("last_verified_on")
                if isinstance(verified, dt.datetime):
                    verified = verified.date()
                elif verified and not isinstance(verified, dt.date):
                    try:
                        verified = dt.datetime.strptime(str(verified).strip(), "%d-%m-%Y").date()
                    except ValueError:
                        errors.append(f"Row {n}: date must be DD-MM-YYYY")
                        continue
                CompetitorPrice.objects.update_or_create(
                    test=test, competitor=comp,
                    defaults={"price": price, "source_note": str(r.get("source") or "price list")[:120],
                              "last_verified_on": verified or timezone.localdate(), "entered_by": request.user})
                ok += 1
        log_event(AuditLog.Action.IMPORT, user=request.user, note=f"Competitor prices upload: {ok} rows, {len(errors)} errors")
        report = {"ok": ok, "errors": errors[:100]}
    return render(request, "pricing/bulk_upload.html", {"report": report})


@admin_required
def template_download(request):
    ds = tablib.Dataset(headers=["test_code", "competitor", "price", "source", "last_verified_on"])
    comps = list(Competitor.objects.filter(is_active=True))
    for t in TestCatalog.objects.filter(is_active=True).order_by("name")[:5]:
        for c in comps[:1]:
            ds.append([t.code, c.name, "", "price list", timezone.localdate().strftime("%d-%m-%Y")])
    resp = HttpResponse(ds.export("xlsx"), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="competitor_prices_template.xlsx"'
    return resp


class CompetitorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Competitor
        fields = ["name", "website", "display_order", "is_active"]


class CompetitorCreateView(AdminRequiredMixin, SimpleFormPageMixin, CreateView):
    model = Competitor
    form_class = CompetitorForm
    page_heading = "Add competitor lab"
    success_url = reverse_lazy("pricing:manage")


class CompetitorUpdateView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    model = Competitor
    form_class = CompetitorForm
    success_url = reverse_lazy("pricing:manage")

