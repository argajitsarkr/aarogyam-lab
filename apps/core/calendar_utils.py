"""Lightweight server-rendered calendar (month / week / day) — no JS library."""
import calendar
import datetime as dt
from collections import defaultdict

from django.utils import timezone

CAL_MODES = ("month", "week", "day")


def parse_anchor(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return timezone.localdate()


def date_range_for(mode, anchor):
    if mode == "day":
        return anchor, anchor
    if mode == "week":
        start = anchor - dt.timedelta(days=anchor.weekday())
        return start, start + dt.timedelta(days=6)
    first = anchor.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    # extend to full weeks for the grid
    return first - dt.timedelta(days=first.weekday()), last + dt.timedelta(days=6 - last.weekday())


def nav_dates(mode, anchor):
    if mode == "day":
        delta = dt.timedelta(days=1)
        return anchor - delta, anchor + delta
    if mode == "week":
        delta = dt.timedelta(days=7)
        return anchor - delta, anchor + delta
    prev_month = (anchor.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    next_month = (anchor.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return prev_month, next_month


def build_calendar(mode, anchor, items, date_attr):
    """Return a structure the `core/_calendar.html` template can render.

    items: iterable of objects; date_attr: callable or attribute name giving the date.
    """
    getter = date_attr if callable(date_attr) else (lambda o: getattr(o, date_attr))
    by_day = defaultdict(list)
    for item in items:
        d = getter(item)
        if d:
            by_day[d].append(item)
    start, end = date_range_for(mode, anchor)
    today = timezone.localdate()
    days = []
    cur = start
    while cur <= end:
        days.append(
            {
                "date": cur,
                "items": by_day.get(cur, []),
                "is_today": cur == today,
                "in_month": cur.month == anchor.month,
            }
        )
        cur += dt.timedelta(days=1)
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    prev, nxt = nav_dates(mode, anchor)
    if mode == "month":
        title = anchor.strftime("%B %Y")
    elif mode == "week":
        title = f"{start.strftime('%d-%m-%Y')} – {end.strftime('%d-%m-%Y')}"
    else:
        title = anchor.strftime("%A, %d-%m-%Y")
    return {
        "mode": mode,
        "modes": CAL_MODES,
        "anchor": anchor,
        "start": start,
        "end": end,
        "days": days,
        "weeks": weeks,
        "prev": prev,
        "next": nxt,
        "title": title,
        "weekday_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }
