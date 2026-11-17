from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory

from apps.centres.models import Centre
from apps.core.forms import StyledFormMixin
from apps.core.validators import normalize_phone, validate_indian_phone

from .models import Doctor, Patient, PinCodeLocation, TestCatalog, Visit, VisitTest


class PatientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["phone", "full_name", "age_years", "dob", "sex", "alt_phone", "email",
                  "house_street", "locality", "village_ward", "city", "district", "state", "pin_code",
                  "consent_to_contact", "do_not_call", "notes"]
        widgets = {
            "dob": forms.DateInput(),
            "notes": forms.Textarea(attrs={"rows": 2}),
            "phone": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 14, "autocomplete": "off"}),
            "alt_phone": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 14}),
            "pin_code": forms.TextInput(attrs={"inputmode": "numeric", "maxlength": 6}),
            "locality": forms.TextInput(attrs={"list": "locality-options", "autocomplete": "off",
                                               "hx-get": "/patients/localities/", "hx-trigger": "keyup changed delay:300ms",
                                               "hx-target": "#locality-options", "hx-swap": "innerHTML"}),
        }
        labels = {"consent_to_contact": "Patient consents to be contacted for follow-ups / re-test reminders"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone"].required = True

    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])

    def clean_alt_phone(self):
        return normalize_phone(self.cleaned_data.get("alt_phone", ""))

    def clean(self):
        data = super().clean()
        if not data.get("age_years") and not data.get("dob"):
            self.add_error("age_years", "Enter age or date of birth.")
        return data


class VisitForm(StyledFormMixin, forms.ModelForm):
    tests = forms.ModelMultipleChoiceField(
        queryset=TestCatalog.objects.none(), widget=forms.MultipleHiddenInput,
        error_messages={"required": "Add at least one test."},
    )
    centre = forms.ModelChoiceField(queryset=Centre.objects.filter(is_active=True), required=False,
                                    help_text="Admins only — employees always register at their home centre.")

    class Meta:
        model = Visit
        fields = ["visit_date", "referring_doctor", "sample_collection_type", "collection_address",
                  "discount", "amount_paid", "payment_mode", "notes"]
        widgets = {"visit_date": forms.DateInput(), "collection_address": forms.Textarea(attrs={"rows": 2}),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["tests"].queryset = TestCatalog.objects.filter(is_active=True)
        self.fields["referring_doctor"].queryset = Doctor.objects.filter(is_active=True)
        if user is None or not user.is_admin:
            del self.fields["centre"]
        else:
            self.fields["centre"].required = True

    def clean(self):
        data = super().clean()
        if data.get("sample_collection_type") == Visit.CollectionType.HOME and not data.get("collection_address"):
            self.add_error("collection_address", "Collection address is required for home collection.")
        tests = data.get("tests") or []
        total = sum(t.price for t in tests)
        if data.get("discount") and data["discount"] > total:
            self.add_error("discount", "Discount cannot exceed the total.")
        return data


class VisitBillingForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Visit
        fields = ["referring_doctor", "discount", "amount_paid", "payment_mode", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class VisitTestResultForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = VisitTest
        fields = ["result_status", "flag", "result_summary", "report_date", "report_pdf"]
        widgets = {"report_date": forms.DateInput()}

    def clean_report_pdf(self):
        f = self.cleaned_data.get("report_pdf")
        if f and hasattr(f, "content_type"):
            if not f.name.lower().endswith(".pdf") or f.content_type not in ("application/pdf", "application/x-pdf"):
                raise ValidationError("Upload a PDF file.")
            if f.size > 10 * 1024 * 1024:
                raise ValidationError("PDF must be under 10 MB.")
            head = f.read(5)
            f.seek(0)
            if head != b"%PDF-":
                raise ValidationError("File is not a valid PDF.")
        return f

    def clean(self):
        data = super().clean()
        if data.get("result_status") == VisitTest.ResultStatus.REPORTED and not data.get("flag"):
            self.add_error("flag", "Set Normal / Borderline / Abnormal when reporting.")
        return data


VisitTestResultFormSet = modelformset_factory(VisitTest, form=VisitTestResultForm, extra=0)


class DoctorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Doctor
        fields = ["name", "clinic", "phone", "specialty", "locality", "is_active"]


class TestCatalogForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TestCatalog
        fields = ["code", "name", "category", "sample_type", "price", "retest_interval_days",
                  "is_chronic_monitoring", "needs_clinical_review", "is_active"]


class PinCodeLocationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PinCodeLocation
        fields = ["pin_code", "label", "latitude", "longitude"]


class ImportUploadForm(StyledFormMixin, forms.Form):
    file = forms.FileField(help_text="Excel (.xlsx) or CSV, first row = column headings. Max 10 MB.")
    centre = forms.ModelChoiceField(queryset=Centre.objects.filter(is_active=True),
                                    help_text="Rows are registered to this centre (unless a 'centre code' column is mapped).")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith((".xlsx", ".csv")):
            raise ValidationError("Upload a .xlsx or .csv file.")
        if f.size > 10 * 1024 * 1024:
            raise ValidationError("File must be under 10 MB.")
        return f


class PhoneField(forms.CharField):
    default_validators = [validate_indian_phone]
