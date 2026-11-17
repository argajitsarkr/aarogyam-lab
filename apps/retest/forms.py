from django import forms

from apps.accounts.models import User
from apps.core.forms import StyledFormMixin

from .models import CallLog


class CallOutcomeForm(StyledFormMixin, forms.Form):
    outcome = forms.ChoiceField(choices=CallLog.Outcome.choices)
    callback_date = forms.DateField(required=False, widget=forms.DateInput())
    booked_date = forms.DateField(required=False, widget=forms.DateInput())
    notes = forms.CharField(required=False, max_length=500)

    def clean(self):
        data = super().clean()
        if data.get("outcome") == CallLog.Outcome.BOOKED and not data.get("booked_date"):
            self.add_error("booked_date", "Enter the booked date.")
        return data


class ReassignForm(forms.Form):
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none())

    def __init__(self, *args, centre=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.active_employees().filter(home_centre=centre)
