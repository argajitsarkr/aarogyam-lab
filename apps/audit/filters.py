import django_filters

from apps.core.filters import StyledFilterSet
from django import forms

from .models import AuditLog


class AuditFilter(StyledFilterSet):
    action = django_filters.ChoiceFilter(choices=AuditLog.Action.choices, empty_label="All actions")
    user = django_filters.CharFilter(field_name="user__username", lookup_expr="icontains", label="User")
    object_repr = django_filters.CharFilter(lookup_expr="icontains", label="Object")
    date_from = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__gte", label="From",
                                          widget=forms.DateInput(attrs={"type": "date"}))
    date_to = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__lte", label="To",
                                        widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = AuditLog
        fields = ["action", "user", "object_repr", "date_from", "date_to"]
