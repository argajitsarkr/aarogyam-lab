"""Visitor counting and rating summaries for the public site.

Both are deliberately cheap and both are real figures: the visitor count is
deduped per IP per day so it is actual traffic, and the rating summary is a
straight aggregate of the reviews people left - nothing here is padded.
"""
from django.core.cache import cache
from django.db.models import Avg, Count, F, Sum
from django.utils import timezone


def client_ip(request):
    # Behind the Cloudflare tunnel nginx forwards the real address in
    # CF-Connecting-IP; X-Forwarded-For is the fallback for a direct proxy.
    for header in ("CF-Connecting-IP", "X-Forwarded-For"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_visit(request):
    """Count this visitor once per day. Deduped by IP in the cache so a visitor
    clicking through ten pages is one visit, not ten."""
    ip = client_ip(request)
    if not ip:
        return
    today = timezone.localdate()
    seen_key = f"visit:{today.isoformat()}:{ip}"
    if cache.get(seen_key):
        return
    cache.set(seen_key, 1, 60 * 60 * 24)

    from .models import DailyVisit

    obj, _ = DailyVisit.objects.get_or_create(date=today)
    DailyVisit.objects.filter(pk=obj.pk).update(count=F("count") + 1)
    cache.delete("visits:total")


def total_visits():
    total = cache.get("visits:total")
    if total is None:
        from .models import DailyVisit

        total = DailyVisit.objects.aggregate(s=Sum("count"))["s"] or 0
        cache.set("visits:total", total, 120)
    return total


def rating_summary(centre=None):
    """Average rating and count, for one centre or the lab overall. Cached for a
    minute: it sits on the home page and every centre card."""
    key = f"reviews:summary:{centre.pk if centre else 'all'}"
    data = cache.get(key)
    if data is None:
        from .models import Review

        qs = Review.objects.published()
        if centre is not None:
            qs = qs.filter(centre=centre)
        agg = qs.aggregate(avg=Avg("rating"), count=Count("id"))
        data = {
            "avg": round(agg["avg"], 1) if agg["avg"] is not None else None,
            "count": agg["count"] or 0,
        }
        cache.set(key, data, 60)
    return data


def clear_rating_cache(centre_pk=None):
    cache.delete("reviews:summary:all")
    if centre_pk is not None:
        cache.delete(f"reviews:summary:{centre_pk}")
