from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import TemplateView

admin.site.site_header = "Aarogyam Pathology — System Admin"
# Only role=Admin users may use the Django admin (reference data, PIN map points);
# the app's own login page is the only sign-in screen.
admin.site.has_permission = lambda request: request.user.is_active and getattr(request.user, "is_admin", False)
admin.site.login = lambda request, extra_context=None: redirect("accounts:login")

# Two halves, kept apart by their url prefix so the login gate, the no-index
# header and robots.txt can tell them apart by path alone (see STAFF_URL_PREFIX
# in apps/core/middleware.py). Everything the staff use lives under /staff/;
# the public site owns the rest of the tree.
staff_patterns = [
    path("", include("apps.dashboard.urls")),
    path("centres/", include("apps.centres.urls")),
    path("patients/", include("apps.patients.urls")),
    path("followups/", include("apps.followups.urls")),
    path("retest/", include("apps.retest.urls")),
    path("pricing/", include("apps.pricing.urls")),
    path("audit/", include("apps.audit.urls")),
    path("core/", include("apps.core.urls")),
]

urlpatterns = [
    path("staff/", include(staff_patterns)),
    path("accounts/", include("apps.accounts.urls")),
    path("system-admin/", admin.site.urls),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    # Last: the public site takes the root, so it must not shadow the above.
    path("", include("apps.public.urls")),
]

handler403 = "apps.core.views.permission_denied"
