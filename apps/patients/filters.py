import django_filters
from django import forms
from django.db.models import Exists, OuterRef, Q

from apps.centres.models import Centre
from apps.core.filters import StyledFilterSet
from apps.core.validators import normalize_phone

from .models import Doctor, Patient, TestCatalog, Visit, VisitTest


class PatientFilter(StyledFilterSet):
    q = django_filters.CharFilter(method="search", label="Search name / phone / patient ID",
                                  widget=forms.TextInput(attrs={"type": "search", "placeholder": "Name, phone or ID…", "autofocus": True}))
    locality = django_filters.CharFilter(lookup_expr="icontains", label="Locality")
    pin_code = django_filters.CharFilter(lookup_expr="startswith", label="PIN code")
    centre = django_filters.ModelChoiceFilter(queryset=Centre.objects.filter(is_active=True), method="by_centre",
                                              label="Visited centre", empty_label="Any centre")
    test = django_filters.ModelChoiceFilter(queryset=TestCatalog.objects.filter(is_active=True), method="by_test",
                                            label="Test", empty_label="Any test")
    doctor = django_filters.ModelChoiceFilter(queryset=Doctor.objects.filter(is_active=True), method="by_doctor",
                                              label="Referring doctor", empty_label="Any doctor")
    flag = django_filters.ChoiceFilter(choices=VisitTest.Flag.choices, method="by_flag", label="Result flag", empty_label="Any flag")
    visit_from = django_filters.DateFilter(method="by_visit_from", label="Visited from", widget=forms.DateInput(attrs={"type": "date"}))
    visit_to = django_filters.DateFilter(method="by_visit_to", label="Visited to", widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = Patient
        fields = ["q", "locality", "pin_code", "centre", "test", "doctor", "flag", "visit_from", "visit_to"]

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, request=request, **kwargs)
        if request and not request.user.is_admin:
            self.filters.pop("centre")
            self.form.fields.pop("centre", None)

    def search(self, qs, name, value):
        value = value.strip()
        phone = normalize_phone(value)
        cond = Q(full_name__icontains=value) | Q(patient_id__icontains=value)
        if phone and phone.isdigit():
            cond |= Q(phone__startswith=phone) | Q(alt_phone__startswith=phone)
        return qs.filter(cond)

    def _visits(self):
        return Visit.objects.filter(patient=OuterRef("pk"), deleted_at__isnull=True)

    def by_centre(self, qs, name, value):
        return qs.filter(Exists(self._visits().filter(centre=value)) | Q(registered_at_centre=value))

    def by_test(self, qs, name, value):
        return qs.filter(Exists(VisitTest.objects.filter(patient=OuterRef("pk"), test=value)))

    def by_doctor(self, qs, name, value):
        return qs.filter(Exists(self._visits().filter(referring_doctor=value)))

    def by_flag(self, qs, name, value):
        tests = VisitTest.objects.filter(patient=OuterRef("pk"), flag=value)
        test = self.form.cleaned_data.get("test")
        if test:
            tests = tests.filter(test=test)
        vf, vt = self.form.cleaned_data.get("visit_from"), self.form.cleaned_data.get("visit_to")
        if vf:
            tests = tests.filter(visit__visit_date__gte=vf)
        if vt:
            tests = tests.filter(visit__visit_date__lte=vt)
        return qs.filter(Exists(tests))

    def by_visit_from(self, qs, name, value):
        return qs.filter(Exists(self._visits().filter(visit_date__gte=value)))

    def by_visit_to(self, qs, name, value):
        return qs.filter(Exists(self._visits().filter(visit_date__lte=value)))
