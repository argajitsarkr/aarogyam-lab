from django.conf import settings

from .models import SiteSettings


def app_context(request):
    from apps.core.preferences import get_pref

    user = getattr(request, "user", None)
    ctx = {"USE_CDN_ASSETS": settings.USE_CDN_ASSETS or settings.DEBUG and not _built_css_exists()}
    if not user or not user.is_authenticated:
        return ctx
    from apps.centres.models import Centre

    ctx.update(
        {
            "scope": request.scope,
            "site_settings": SiteSettings.load(),
            "is_admin_user": user.is_admin,
            "pinned_filters": user.saved_filters.filter(pinned=True)[:12],
            # Sidebar collapsed to an icon rail? Remembered per user (B4).
            "sidebar_rail": bool(get_pref(user, "ui:sidebar_rail", False)),
            # Website enquiries nobody has picked up yet. Cached, because it is
            # on every staff page and nothing breaks if it is a minute stale.
            "open_enquiries": _open_enquiry_count(),
        }
    )
    if user.is_admin:
        ctx["switcher_centres"] = Centre.objects.filter(is_active=True).order_by("-is_head_centre", "name")
    return ctx


_css_cache = {}


def _built_css_exists():
    if "v" not in _css_cache:
        from django.contrib.staticfiles import finders

        _css_cache["v"] = bool(finders.find("dist/app.css"))
    return _css_cache["v"]


def _open_enquiry_count():
    from django.core.cache import cache

    count = cache.get("enquiries:open")
    if count is None:
        from apps.public.models import Enquiry

        count = Enquiry.objects.filter(status=Enquiry.Status.NEW).count()
        cache.set("enquiries:open", count, 60)
    return count
