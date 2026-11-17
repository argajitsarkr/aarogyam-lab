from apps.core.mixins import AdminRequiredMixin, ListPageMixin

from .filters import AuditFilter
from .models import AuditLog


class AuditLogListView(AdminRequiredMixin, ListPageMixin):
    model = AuditLog
    page_key = "audit"
    url_name = "audit:list"
    template_name = "audit/list.html"
    results_template = "audit/_results.html"
    filterset_class = AuditFilter
    results_label = "entry"
    view_modes = ("table", "card")
    sort_fields = {"timestamp": "timestamp", "action": "action", "user": "user__username"}
    default_sort = "-timestamp"
    paginate_by = 50
    columns = [("timestamp", "When"), ("user", "User"), ("centre", "Centre"), ("action", "Action"),
               ("object", "Object"), ("ip", "IP"), ("changes", "Changes")]

    def get_base_queryset(self):
        qs = AuditLog.objects.select_related("user", "centre", "content_type")
        if self.request.scope.mode == "centre":
            qs = qs.filter(centre_id__in=self.request.scope.centre_ids)
        return qs
