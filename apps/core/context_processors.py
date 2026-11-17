from django.conf import settings

from .models import SiteSettings


def app_context(request):
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
