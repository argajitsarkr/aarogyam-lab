"""Balanced round-robin assignment of work items to a centre's employees."""
from django.db.models import Count, Q


def pick_assignee(centre, related_name, open_statuses):
    """Return the active employee at `centre` with the fewest open items
    (ties broken by user id, so consecutive items rotate through staff)."""
    from apps.accounts.models import User

    status_filter = Q(**{f"{related_name}__status__in": open_statuses})
    return (
        User.objects.active_employees()
        .filter(home_centre=centre)
        .annotate(load=Count(related_name, filter=status_filter))
        .order_by("load", "pk")
        .first()
    )
