from django import forms

from apps.accounts.models import User
from apps.centres.models import Centre
from apps.core.forms import StyledFormMixin
from apps.patients.models import Doctor

from .models import FollowUp


class FollowUpForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ["reason", "referring_doctor", "due_date", "priority", "assigned_to", "next_action_date", "notes"]
        widgets = {"due_date": forms.DateInput(), "next_action_date": forms.DateInput(),
                   "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, centre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["referring_doctor"].queryset = Doctor.objects.filter(is_active=True)
        staff = User.objects.active_employees()
        if centre:
            staff = staff.filter(home_centre=centre)
        self.fields["assigned_to"].queryset = staff
        self.fields["assigned_to"].help_text = "Leave blank to auto-assign (balanced round-robin)."


class StatusUpdateForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(choices=FollowUp.Status.choices)
    scheduled_date = forms.DateField(required=False, widget=forms.DateInput(), help_text="Required when Scheduled.")
    scheduled_centre = forms.ModelChoiceField(queryset=Centre.objects.filter(is_active=True), required=False)
    next_action_date = forms.DateField(required=False, widget=forms.DateInput())
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Contact note")

    def clean(self):
        data = super().clean()
        if data.get("status") == FollowUp.Status.SCHEDULED and not data.get("scheduled_date"):
            self.add_error("scheduled_date", "Enter the appointment date.")
        return data
