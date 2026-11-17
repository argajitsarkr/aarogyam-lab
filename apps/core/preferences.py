"""Per-user UI preferences (stored on User.ui_preferences JSON field).

Keys used across the app:
    scope                      -> "all" | "centre:<id>"   (admins only)
    view:<page>                -> "table" | "card" | "kanban" | "calendar"
    cols:<page>                -> list of hidden column keys
    page_size:<page>           -> 25 | 50 | 100
    cal:<page>                 -> "month" | "week" | "day"
"""

PAGE_SIZES = (25, 50, 100)


def get_pref(user, key, default=None):
    if not user.is_authenticated:
        return default
    return (user.ui_preferences or {}).get(key, default)


def set_pref(user, key, value):
    if not user.is_authenticated:
        return
    prefs = dict(user.ui_preferences or {})
    if prefs.get(key) == value:
        return
    prefs[key] = value
    user.ui_preferences = prefs
    # update only this column: avoids clobbering other fields / audit noise
    from django.contrib.auth import get_user_model

    get_user_model().objects.filter(pk=user.pk).update(ui_preferences=prefs)
