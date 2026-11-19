from django import forms

from .models import Enquiry


class EnquiryHandleForm(forms.ModelForm):
    """What a staff member records after calling the person back."""

    class Meta:
        model = Enquiry
        fields = ["status", "staff_notes"]
        widgets = {"staff_notes": forms.Textarea(attrs={"rows": 4, "placeholder": "What happened on the call?"})}
