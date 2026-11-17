from django import forms

from apps.core.forms import StyledFormMixin
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.centres.models import Centre

from .models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username or phone", widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}))


class ForcedPasswordChangeForm(PasswordChangeForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.must_change_password = False
        if commit:
            user.save()
        return user


class UserForm(StyledFormMixin, forms.ModelForm):
    password = forms.CharField(
        label="Temporary password", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Min 10 characters. The user must change it on first login. Leave blank to keep the current password.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "phone", "email", "role", "home_centre", "extra_centres", "is_active"]
        widgets = {"extra_centres": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["home_centre"].queryset = Centre.objects.filter(is_active=True)
        self.fields["extra_centres"].queryset = Centre.objects.filter(is_active=True)
        if not self.instance.pk:
            self.fields["password"].required = True

    def clean_password(self):
        pw = self.cleaned_data.get("password")
        if pw:
            validate_password(pw, self.instance)
        return pw

    def clean(self):
        data = super().clean()
        if data.get("role") == User.Role.EMPLOYEE and not data.get("home_centre"):
            self.add_error("home_centre", "Employees must have a home centre.")
        return data

    def _post_clean(self):
        # Model.full_clean (via super) runs User.clean which enforces caps.
        super()._post_clean()

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        if pw:
            user.set_password(pw)
            user.must_change_password = True
        if user.role == User.Role.ADMIN:
            # Admins get the (restricted) system-admin site too
            user.is_staff = user.is_superuser = True
        if commit:
            try:
                user.save()
            except ValidationError as exc:  # race: caps re-checked at save time
                raise forms.ValidationError(exc.messages)
            self.save_m2m()
        return user
