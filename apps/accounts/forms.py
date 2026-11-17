from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username or email", widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}))


class ForcedPasswordChangeForm(PasswordChangeForm):
    def clean_new_password1(self):
        new = self.cleaned_data.get("new_password1")
        if new and self.user.check_password(new):
            raise ValidationError("New password must be different from the current one.")
        return new

    def save(self, commit=True):
        user = super().save(commit=False)
        user.must_change_password = False
        if commit:
            user.save()
        return user
