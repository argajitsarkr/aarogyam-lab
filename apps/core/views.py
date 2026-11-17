import json

from django import forms
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView

from .mixins import AdminRequiredMixin, SimpleFormPageMixin
from .models import SavedFilter, SiteSettings
from .preferences import PAGE_SIZES, set_pref

ALLOWED_PREF_PREFIXES = ("view:", "cols:", "page_size:", "cal:", "dash:")


def permission_denied(request, exception=None):
    return render(request, "403.html", {"reason": str(exception or "")}, status=403)


def _safe_next(request, fallback="/"):
    nxt = request.POST.get("next") or request.headers.get("Referer") or fallback
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


@require_POST
def set_scope(request):
    """Top-bar scope switcher. Employees are always pinned to their centre."""
    value = request.POST.get("scope", "all")
    if request.user.is_admin:
        if value == "all" or value.startswith("centre:"):
            set_pref(request.user, "scope", value)
    return redirect(_safe_next(request))


@require_POST
def save_pref(request):
    """Generic preference setter used by Alpine/HTMX widgets (e.g. column toggles)."""
    key = request.POST.get("key", "")
    raw = request.POST.get("value", "")
    if not key.startswith(ALLOWED_PREF_PREFIXES) or len(key) > 60:
        return HttpResponseBadRequest("Invalid key")
    try:
        value = json.loads(raw)
    except ValueError:
        value = raw
    if key.startswith("page_size:") and value not in PAGE_SIZES:
        return HttpResponseBadRequest("Invalid page size")
    if key.startswith("cols:") and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
        return HttpResponseBadRequest("Invalid columns")
    set_pref(request.user, key, value)
    return JsonResponse({"ok": True})


@require_POST
def saved_filter_create(request):
    page = request.POST.get("page", "")
    name = (request.POST.get("name") or "").strip()[:80]
    qs = (request.POST.get("querystring") or "")[:1000]
    try:
        reverse(page)
    except NoReverseMatch:
        return HttpResponseBadRequest("Unknown page")
    if not name:
        messages.error(request, "Please give the saved view a name.")
    else:
        SavedFilter.objects.update_or_create(
            user=request.user, page=page, name=name, defaults={"querystring": qs, "pinned": True}
        )
        messages.success(request, f"Saved view “{name}” pinned to the sidebar.")
    return redirect(_safe_next(request))


@require_POST
def saved_filter_delete(request, pk):
    get_object_or_404(SavedFilter, pk=pk, user=request.user).delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect(_safe_next(request))


@require_POST
def saved_filter_toggle_pin(request, pk):
    sf = get_object_or_404(SavedFilter, pk=pk, user=request.user)
    sf.pinned = not sf.pinned
    sf.save(update_fields=["pinned"])
    return redirect(_safe_next(request))


from .forms import StyledFormMixin


class SiteSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["lab_display_name", "max_active_employees", "retest_lookahead_days", "price_stale_days"]


class SiteSettingsView(AdminRequiredMixin, SimpleFormPageMixin, UpdateView):
    form_class = SiteSettingsForm
    page_heading = "Site settings"
    help_note = "The Admin cap (3) is fixed by policy. A lower employee cap only blocks new activations."

    def get_object(self, queryset=None):
        return SiteSettings.load()

    def form_valid(self, form):
        messages.success(self.request, "Settings saved.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("core:settings")
