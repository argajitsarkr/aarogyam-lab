from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def inr(value):
    """Format a number as Indian Rupees with Indian digit grouping: ₹1,23,456."""
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError):
        return value
    negative = amount < 0
    amount = abs(amount).quantize(Decimal("1"))
    s = str(int(amount))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{'-' if negative else ''}₹{s}"


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Return the current querystring with the given keys replaced."""
    params = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v is None or v == "":
            params.pop(k, None)
        else:
            params[k] = v
    return params.urlencode()


@register.simple_tag(takes_context=True)
def sort_link(context, key, label):
    current = context.get("current_sort") or ""
    if current == key:
        new, arrow = f"-{key}", " ▲"
    elif current == f"-{key}":
        new, arrow = key, " ▼"
    else:
        new, arrow = key, ""
    params = context["request"].GET.copy()
    params["sort"] = new
    params.pop("page", None)
    return format_html(
        '<a href="?{}" hx-get="?{}" hx-target="#list-results" hx-push-url="true" class="hover:underline">{}{}</a>',
        params.urlencode(), params.urlencode(), label, arrow,
    )


def readable_ink(hex_colour, light="#ffffff", dark="#0A0A0B"):
    """Pick whichever of light/dark has more contrast against `hex_colour`.

    A centre's colour is editable, so a badge cannot assume white text: white on
    the orange centre measures 2.5:1, well under the 4.5:1 small text needs, while
    near-black on it is 7.9:1.
    """
    try:
        r, g, b = (int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except (ValueError, AttributeError):
        return light
    def channel(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    luminance = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
    return dark if luminance > 0.35 else light


@register.inclusion_tag("core/_centre_badge.html")
def centre_badge(centre):
    return {"centre": centre, "ink": readable_ink(centre.colour) if centre else "#ffffff"}


@register.filter
def get_item(d, key):
    if d is None:
        return None
    return d.get(key)


FLAG_CLASSES = {
    "NORMAL": "bg-emerald-100 text-emerald-800",
    "BORDERLINE": "bg-amber-100 text-amber-800",
    "ABNORMAL": "bg-red-100 text-red-800",
    "HIGH": "bg-red-100 text-red-800",
    "MEDIUM": "bg-amber-100 text-amber-800",
    "LOW": "bg-slate-100 text-slate-700",
    "PENDING": "bg-slate-100 text-slate-700",
    "CONTACTED": "bg-sky-100 text-sky-800",
    "SCHEDULED": "bg-indigo-100 text-indigo-800",
    "COMPLETED": "bg-emerald-100 text-emerald-800",
    "CONVERTED": "bg-emerald-100 text-emerald-800",
    "NOT_INTERESTED": "bg-zinc-200 text-zinc-700",
    "UNREACHABLE": "bg-zinc-200 text-zinc-700",
    "CLOSED": "bg-zinc-200 text-zinc-700",
    "REPORTED": "bg-emerald-100 text-emerald-800",
}


@register.simple_tag
def pill(code, label=None):
    cls = FLAG_CLASSES.get(str(code), "bg-slate-100 text-slate-700")
    return format_html('<span class="inline-block rounded-full px-2 py-0.5 text-xs font-medium {}">{}</span>', cls, label or code)


@register.filter
def minutes(td):
    """timedelta -> whole minutes (at least 1), e.g. for the account-locked page."""
    try:
        return max(1, int(td.total_seconds() // 60))
    except AttributeError:
        return td


# Google Material Symbols (Rounded). Loaded as a variable font in templates/_assets.html;
# the ligature name is the glyph, e.g. {% icon "call" %} -> <span class="mi">call</span>.
@register.simple_tag
def icon(name, cls=""):
    """Render a Material Symbols icon. Decorative by default: screen readers skip it and
    read the adjacent label instead, so every icon needs visible text or a title/aria-label
    on its control."""
    return format_html('<span class="mi {}" aria-hidden="true" translate="no">{}</span>', cls, name)


@register.simple_tag
def nav_item(url_name, icon_name, label, page_name="", match=""):
    """One tab in the public site's category ribbon.

    The active tab is decided by the view's `page_name`, not by comparing paths:
    a test detail page has to light up "Lab Test" even though its url is
    /lab-tests/<code>/.
    """
    from django.urls import reverse

    is_active = bool(match) and page_name == match
    link_cls = (
        "border-teal-700 text-teal-700" if is_active else "border-transparent text-slate-600 hover:text-teal-700"
    )
    return format_html(
        '<li><a href="{}" class="pub-nav flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-3 {}"{}>'
        '<span class="mi" aria-hidden="true" translate="no">{}</span>{}</a></li>',
        reverse(url_name),
        link_cls,
        format_html(' aria-current="page"') if is_active else "",
        icon_name,
        label,
    )
