"""Centre scoping — the single source of truth for "which centres can this user see".

Every list/detail view goes through these helpers (via the mixins in
`apps.core.mixins`) so scoping is enforced in querysets, not just templates.
"""
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied
from django.db import models


@dataclass
class Scope:
    mode: str  # "mine" | "all" | "centre"
    centre_ids: list = field(default_factory=list)
    label: str = ""
    centre: object = None  # set when a single centre is selected

    @property
    def is_multi(self):
        return self.mode == "all"


def resolve_scope(user):
    """Work out the active scope for this user from their saved preference.

    Employees are always pinned to their home centre. Admins choose between
    all centres (default) or one specific centre via the top-bar switcher.
    """
    from apps.centres.models import Centre

    if not user.is_authenticated:
        return Scope(mode="mine")
    if not user.is_admin:
        centre = user.home_centre
        return Scope(mode="mine", centre_ids=[centre.pk] if centre else [], label=centre.name if centre else "—", centre=centre)

    pref = (user.ui_preferences or {}).get("scope", "all")
    if pref.startswith("centre:"):
        try:
            centre = Centre.objects.get(pk=int(pref.split(":", 1)[1]), is_active=True)
            return Scope(mode="centre", centre_ids=[centre.pk], label=centre.name, centre=centre)
        except (ValueError, Centre.DoesNotExist):
            pass
    ids = list(Centre.objects.filter(is_active=True).values_list("pk", flat=True))
    return Scope(mode="all", centre_ids=ids, label="All Centres")


class CentreScopedQuerySet(models.QuerySet):
    """QuerySet with helpers for models that carry a `centre` FK."""

    centre_field = "centre"

    def for_centres(self, centre_ids):
        return self.filter(**{f"{self.centre_field}__in": centre_ids})

    def for_scope(self, scope):
        return self.for_centres(scope.centre_ids)

    def accessible_to(self, user):
        return self.for_centres(user.accessible_centre_ids())


def check_centre_access(user, centre_id):
    """Raise PermissionDenied if the user may not touch rows of this centre."""
    if centre_id not in user.accessible_centre_ids():
        raise PermissionDenied("You do not have access to this centre's records.")
