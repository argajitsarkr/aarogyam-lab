import django_filters
from django import forms
from django.db.models import Q

from apps.accounts.models import User
from apps.centres.models import Centre
from apps.core.filters import StyledFilterSet

from .models import FollowUp


class FollowUpFilter(StyledFilterSet):
    q = django_filters.CharFilter(method="search", label="Patient",
                                  widget=forms.TextInput(attrs={"type": "search", "placeholder": "Name, phone, ID…"}))
    centre = django_filters.ModelChoiceFilter(queryset=Centre.objects.filter(is_active=True), empty_label="Any centre")
    assigned_to = django_filters.ModelChoiceFilter(queryset=User.objects.none(), label="Employee", empty_label="Anyone")
    reason = django_filters.ChoiceFilter(choices=FollowUp.Reason.choices, empty_label="Any reason")
    priority = django_filters.ChoiceFilter(choices=FollowUp.Priority.choices, empty_label="Any priority")
    status = django_filters.ChoiceFilter(choices=FollowUp.Status.choices, empty_label="Any status")

    class Meta:
        model = FollowUp
        fields = ["q", "centre", "assigned_to", "reason", "priority", "status"]

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, request=request, **kwargs)
        staff = User.objects.active_employees()
        if request and not request.user.is_admin:
            self.filters.pop("centre")
            self.form.fields.pop("centre", None)
            staff = staff.filter(home_centre=request.user.home_centre)
        self.form.fields["assigned_to"].queryset = staff
        self.filters["assigned_to"].queryset = staff

    def search(self, qs, name, value):
        return qs.filter(Q(patient__full_name__icontains=value) | Q(patient__phone__startswith=value)
                         | Q(patient__patient_id__icontains=value))
