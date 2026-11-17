from django import forms

from apps.accounts.models import User
from apps.core.forms import StyledFormMixin

from .models import Centre


class CentreForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Centre
        fields = ["name", "short_code", "address", "locality", "city", "district", "state", "pin_code",
                  "latitude", "longitude", "contact_phone", "in_charge", "colour", "is_head_centre", "is_active"]
        widgets = {"colour": forms.TextInput(attrs={"type": "color"}), "address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["in_charge"].queryset = User.objects.filter(is_active=True)
        if self.instance.pk and self.instance.patients_registered.exists():
            self.fields["short_code"].disabled = True
