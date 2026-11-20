"""Everything the public header and footer need, on every public page.

Cached for five minutes: these are three small queries that would otherwise run
on every visit, and the content changes a few times a year.
"""
from django.core.cache import cache

PUBLIC_NAV_CACHE_KEY = "public:nav"
PUBLIC_NAV_TTL = 300


def public_nav(request):
    if not getattr(request, "is_public_page", False):
        return {}
    data = cache.get(PUBLIC_NAV_CACHE_KEY)
    if data is None:
        from apps.centres.models import Centre
        from apps.core.models import SiteSettings

        from .models import MedicineCategory

        data = {
            "nav_centres": list(Centre.objects.filter(is_active=True, is_public=True)),
            "nav_medicine_categories": list(MedicineCategory.objects.published()[:8]),
            "site_settings": SiteSettings.load(),
        }
        cache.set(PUBLIC_NAV_CACHE_KEY, data, PUBLIC_NAV_TTL)

    # Count the visit and hand the footer the running total. Kept out of the
    # cached block above because the total changes while the nav does not; both
    # the de-dupe and the total are themselves cached, so this stays cheap.
    from .stats import record_visit, total_visits

    record_visit(request)
    return {**data, "visitor_count": total_visits()}


def clear_public_nav_cache(**_kwargs):
    cache.delete(PUBLIC_NAV_CACHE_KEY)
