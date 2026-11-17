from django import forms

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
