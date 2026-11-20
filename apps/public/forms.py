from django import forms

from .models import Enquiry, Review

MAX_PRESCRIPTION_BYTES = 8 * 1024 * 1024
ALLOWED_PRESCRIPTION_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}


class EnquiryForm(forms.ModelForm):
    """The single public form. Every call-to-action on the site posts this; the
    `kind` decides which fields the template shows and which are required."""

    # A bot trap. Real visitors never see it, so anything in it is spam - the
    # view marks that enquiry SPAM rather than rejecting it, so a false positive
    # is still visible to the staff instead of lost.
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    # Declared wider than the model's 10 characters on purpose. People type
    # "+91 98765 43210"; the model field's max_length runs BEFORE clean_phone,
    # so inheriting it would reject the number before there is a chance to
    # strip it. clean_phone narrows it to ten digits, and the model validator
    # still has the last word in _post_clean.
    phone = forms.CharField(
        max_length=18,
        widget=forms.TextInput(attrs={
            "placeholder": "10-digit mobile number", "inputmode": "numeric",
            "autocomplete": "tel-national", "maxlength": "18",
        }),
    )

    class Meta:
        model = Enquiry
        fields = ["kind", "name", "phone", "centre", "test", "message", "prescription"]
        widgets = {
            "kind": forms.HiddenInput,
            "test": forms.HiddenInput,
            "name": forms.TextInput(attrs={"placeholder": "Your name", "autocomplete": "name"}),
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Anything we should know? (optional)"}),
        }
        labels = {"centre": "Nearest centre", "message": "Message"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.centres.models import Centre

        self.fields["centre"].queryset = Centre.objects.filter(is_active=True, is_public=True)
        self.fields["centre"].required = False
        self.fields["centre"].empty_label = "Any centre"
        self.fields["prescription"].required = False
        self.fields["message"].required = False

        # The centre select and the message box are rendered by Django, not by
        # hand like name and phone, so without this they come out as the
        # browser's raw grey widgets next to the styled inputs - which is what
        # read as "messy". Give them the same shape as the hand-written fields.
        field_class = (
            "mt-1 w-full rounded-lg border-slate-300 shadow-sm "
            "focus:border-teal-700 focus:ring-teal-700"
        )
        self.fields["centre"].widget.attrs["class"] = field_class
        self.fields["message"].widget.attrs["class"] = field_class

    def clean_phone(self):
        # Visitors type spaces, +91 and dashes. Strip to the ten digits the
        # model validator wants rather than scolding them about format.
        raw = (self.cleaned_data.get("phone") or "").strip()
        digits = "".join(c for c in raw if c.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        return digits

    def clean_prescription(self):
        f = self.cleaned_data.get("prescription")
        if not f:
            return f
        if f.size > MAX_PRESCRIPTION_BYTES:
            raise forms.ValidationError("That file is over 8 MB. A phone photo of the prescription is enough.")
        if getattr(f, "content_type", None) and f.content_type not in ALLOWED_PRESCRIPTION_TYPES:
            raise forms.ValidationError("Please attach a photo (JPG, PNG) or a PDF.")
        return f

    def clean(self):
        data = super().clean()
        if data.get("kind") == Enquiry.Kind.PRESCRIPTION and not data.get("prescription"):
            self.add_error("prescription", "Please attach a photo of the prescription.")
        return data

    @property
    def kind_value(self):
        """Which variant of this form is on screen.

        Read from the POSTed data first and `initial` only as a fallback: on a
        re-render after a failed submit there is no `initial`, and a template
        that asked `initial.kind` would drop the file field - and with it the
        validation error telling the visitor to attach the prescription.
        """
        return (
            self.data.get(self.add_prefix("kind"))
            or self.initial.get("kind")
            or Enquiry.Kind.CALLBACK
        )

    @property
    def is_prescription(self):
        return self.kind_value == Enquiry.Kind.PRESCRIPTION

    @property
    def looks_like_spam(self):
        return bool(self.data.get(self.add_prefix("website")))


class ReviewForm(forms.ModelForm):
    """The form behind the QR code. The centre is fixed by the QR (passed in by
    the view), so the visitor only gives their name, a star rating and - if they
    like - a line about the visit."""

    website = forms.CharField(required=False, widget=forms.HiddenInput)  # honeypot

    class Meta:
        model = Review
        fields = ["name", "rating", "comment"]
        widgets = {
            "name": forms.TextInput(attrs={
                "placeholder": "Your name", "autocomplete": "name", "maxlength": "80",
            }),
            "rating": forms.HiddenInput,  # set by the star control in the template
            "comment": forms.Textarea(attrs={
                "rows": 3, "placeholder": "A few words about your visit (optional)", "maxlength": "500",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comment"].required = False
        field_class = (
            "mt-1 w-full rounded-lg border-slate-300 shadow-sm focus:border-teal-700 focus:ring-teal-700"
        )
        self.fields["name"].widget.attrs["class"] = field_class
        self.fields["comment"].widget.attrs["class"] = field_class

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if not rating or not (1 <= rating <= 5):
            raise forms.ValidationError("Please tap a star rating.")
        return rating

    @property
    def looks_like_spam(self):
        return bool(self.data.get(self.add_prefix("website")))
