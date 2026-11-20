from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView

from .preferences import PAGE_SIZES, get_pref, set_pref


def is_admin(user):
    return user.is_authenticated and getattr(user, "is_admin", False)


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_admin(request.user):
            raise PermissionDenied("Admins only.")
        return super().dispatch(request, *args, **kwargs)


def admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("Admins only.")
        return view_func(request, *args, **kwargs)

    return wrapper


class ScopedQuerysetMixin:
    """Restricts a model's queryset to the request's active centre scope.

    `scope_lookup` is the ORM path to the Centre FK (e.g. "centre" or
    "visit__centre").
    """

    scope_lookup = "centre"

    def scope_queryset(self, qs):
        return qs.filter(**{f"{self.scope_lookup}__in": self.request.scope.centre_ids})


class ListPageMixin(LoginRequiredMixin, ScopedQuerysetMixin, ListView):
    """Shared behaviour for every list page: scope, filters, sorting,
    table/card/kanban/calendar view switching, column visibility, page size,
    saved filters. Preferences persist on the user profile."""

    page_key = None  # e.g. "patients" — also the preference key
    results_label = "result"  # noun for the results header: "128 patients"
    url_name = None  # e.g. "patients:list" — used for saved filters
    view_modes = ("table", "card")
    default_view = "table"
    filterset_class = None
    sort_fields = {}
    default_sort = None
    columns = []  # list of (key, label)
    results_template = None
    paginate_by = 25

    # ---- view mode --------------------------------------------------------
    def get_view_mode(self):
        if hasattr(self, "_view_mode"):
            return self._view_mode
        requested = self.request.GET.get("view")
        key = f"view:{self.page_key}"
        if requested in self.view_modes:
            set_pref(self.request.user, key, requested)
            mode = requested
        else:
            mode = get_pref(self.request.user, key, self.default_view)
            if mode not in self.view_modes:
                mode = self.default_view
        self._view_mode = mode
        return mode

    def get_paginate_by(self, queryset):
        if self.get_view_mode() in ("kanban", "calendar"):
            return None
        key = f"page_size:{self.page_key}"
        try:
            size = int(self.request.GET.get("page_size", 0))
        except ValueError:
            size = 0
        if size in PAGE_SIZES:
            set_pref(self.request.user, key, size)
            return size
        return get_pref(self.request.user, key, self.paginate_by)

    # ---- queryset ---------------------------------------------------------
    def get_base_queryset(self):
        return self.scope_queryset(super().get_queryset())

    def get_sort(self):
        sort = self.request.GET.get("sort") or self.default_sort
        if sort and sort.lstrip("-") in self.sort_fields:
            return sort
        return self.default_sort

    def get_queryset(self):
        qs = self.get_base_queryset()
        self.filterset = None
        if self.filterset_class:
            self.filterset = self.filterset_class(self.request.GET or None, queryset=qs, request=self.request)
            qs = self.filterset.qs
        sort = self.get_sort()
        if sort:
            desc = sort.startswith("-")
            field = self.sort_fields[sort.lstrip("-")]
            qs = qs.order_by(f"-{field}" if desc else field, "-pk")
        return qs

    # ---- one-click pill filter (C7) ----------------------------------------
    def _pill_context(self):
        """Render one filter as pills instead of a select: the one people change
        every day. The filterset names it in `pill_field`."""
        fs = getattr(self, "filterset", None)
        name = getattr(fs, "pill_field", None) if fs else None
        if not name or name not in fs.form.fields:
            return {"pill_field": None, "pill_choices": []}
        field = fs.form[name]
        choices = [(v, label) for v, label in fs.form.fields[name].choices if v != ""]
        return {"pill_field": field, "pill_choices": choices}

    # ---- templates & context ----------------------------------------------
    def get_template_names(self):
        if self.request.headers.get("HX-Request") and self.request.headers.get("HX-Target") == "list-results":
            return [self.results_template]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        params.pop("view", None)
        hidden = get_pref(self.request.user, f"cols:{self.page_key}", [])
        ctx.update(
            {
                "view_mode": self.get_view_mode(),
                "view_modes": self.view_modes,
                "filter": getattr(self, "filterset", None),
                "current_sort": self.get_sort(),
                "columns": [(k, label, k not in hidden) for k, label in self.columns],
                "hidden_cols": hidden,
                "page_key": self.page_key,
                "url_name": self.url_name,
                "page_sizes": PAGE_SIZES,
                "querystring": params.urlencode(),
                "filter_querystring": _filter_qs(params),
                "results_template": self.results_template,
                "saved_filters": self.request.user.saved_filters.filter(page=self.url_name),
                "results_label": self.results_label,
            }
        )
        ctx.update(self._pill_context())
        return ctx


class KanbanCalendarMixin:
    """Kanban-column and calendar context for a ListPageMixin list page.

    Both the re-test queue and the follow-up list are the same kind of board - a
    status lifecycle shown as columns, and a due/appointment date shown on a
    calendar - so the context that builds them lives here once. A view opts in by
    setting `status_enum`, `kanban_columns` and `calendar_pref_key`; its items
    need a `status` and a `calendar_date` (overridable via `calendar_date_attr`).
    The model-specific part - which rows belong in each mode - stays in the
    view's `get_base_queryset`.
    """

    status_enum = None
    kanban_columns = ()
    calendar_pref_key = None
    calendar_date_attr = "calendar_date"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mode = self.get_view_mode()
        if mode == "kanban":
            items = list(ctx["object_list"])
            ctx["kanban"] = [
                (s, self.status_enum(s).label, [i for i in items if i.status == s])
                for s in self.kanban_columns
            ]
        elif mode == "calendar":
            ctx["cal"] = self._calendar_context(list(ctx["object_list"]))
        return ctx

    def _calendar_context(self, items):
        from .calendar_utils import CAL_MODES, build_calendar, date_range_for, parse_anchor

        cal_mode = self.request.GET.get("cal") or get_pref(self.request.user, self.calendar_pref_key, "month")
        if cal_mode not in CAL_MODES:
            cal_mode = "month"
        set_pref(self.request.user, self.calendar_pref_key, cal_mode)
        anchor = parse_anchor(self.request.GET.get("d"))
        start, end = date_range_for(cal_mode, anchor)
        attr = self.calendar_date_attr
        visible = [i for i in items if getattr(i, attr) and start <= getattr(i, attr) <= end]
        return build_calendar(cal_mode, anchor, visible, attr)


def _filter_qs(params):
    p = params.copy()
    for k in ("sort", "page_size"):
        p.pop(k, None)
    return p.urlencode()


class SimpleFormPageMixin:
    """Renders a ModelForm with the shared `core/_simple_form_page.html`."""

    template_name = "core/_simple_form_page.html"
    page_heading = ""
    cancel_url = None
    help_note = ""

    def get_page_heading(self):
        obj = getattr(self, "object", None)
        return self.page_heading or (f"Edit {obj}" if obj else "New")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cancel = self.cancel_url or (str(self.success_url) if getattr(self, "success_url", None) else None)
        if cancel is None and getattr(self, "object", None) is not None:
            cancel = self.get_success_url()
        ctx.update(page_heading=self.get_page_heading(), cancel_url=cancel,
                   help_note=self.help_note)
        return ctx
