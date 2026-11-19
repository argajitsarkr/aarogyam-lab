from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import TemplateView

from apps.public.sitemaps import SITEMAPS

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
    path("enquiries/", include("apps.public.staff_urls")),
]

urlpatterns = [
    path("staff/", include(staff_patterns)),
    path("accounts/", include("apps.accounts.urls")),
    path("system-admin/", admin.site.urls),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    # Last: the public site takes the root, so it must not shadow the above.
    path("", include("apps.public.urls")),
]

# The dev server has no nginx in front of it, so it serves the uploaded photos
# itself. In production nginx owns /media/ and this adds nothing.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "apps.core.views.permission_denied"
