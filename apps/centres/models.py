from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.validators import validate_indian_phone, validate_pin_code

TRIPURA_DISTRICTS = [
    "West Tripura", "Sepahijala", "Khowai", "Gomati", "South Tripura",
    "Dhalai", "Unakoti", "North Tripura",
]
DISTRICT_CHOICES = [(d, d) for d in TRIPURA_DISTRICTS] + [("Other", "Other")]


class Centre(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    short_code = models.CharField(
        max_length=5, unique=True,
        validators=[RegexValidator(r"^[A-Z]{2,5}$", "2–5 uppercase letters, e.g. ARP")],
        help_text="Used as the prefix of patient IDs, e.g. ARP-2026-000123. Cannot be changed once patients exist.",
    )
    address = models.TextField(blank=True)
    locality = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=80, default="Agartala")
    district = models.CharField(max_length=40, choices=DISTRICT_CHOICES, default="West Tripura")
    state = models.CharField(max_length=60, default="Tripura")
    pin_code = models.CharField(max_length=6, blank=True, validators=[validate_pin_code])
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_phone = models.CharField(max_length=10, blank=True, validators=[validate_indian_phone])
    in_charge = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="centres_in_charge"
    )
    colour = models.CharField(max_length=7, default="#0f766e", help_text="Hex colour for badges, e.g. #0f766e")
    is_head_centre = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # ---- public site ------------------------------------------------------
    # A centre can be live for the staff and not yet shown to the public (no
    # photo, hours not confirmed), so listing is a separate switch.
    is_public = models.BooleanField(
        default=False, verbose_name="Show on the public site",
        help_text="Off until the photo and opening hours are confirmed.",
    )
    public_blurb = models.CharField(max_length=200, blank=True, help_text="One line under the centre name.")
    opening_hours = models.TextField(blank=True, help_text="One line per day or range, e.g. 'Mon-Sat  7:00 am - 8:00 pm'.")
    whatsapp = models.CharField(
        max_length=10, blank=True, validators=[validate_indian_phone],
        help_text="Blank falls back to the contact phone.",
    )
    photo = models.ImageField(upload_to="centres/", blank=True)
    map_url = models.URLField(blank=True, help_text="Google Maps link for the Directions button.")

    class Meta:
        ordering = ["-is_head_centre", "name"]

    def __str__(self):
        return self.name

    @property
    def slug(self):
        """The public url segment. The short code is already unique and stable -
        it is the prefix of every patient ID - so there is no slug field."""
        return self.short_code.lower()

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("public:centre", args=[self.slug])

    @property
    def hours_lines(self):
        return [line.strip() for line in self.opening_hours.splitlines() if line.strip()]

    @property
    def whatsapp_number(self):
        return self.whatsapp or self.contact_phone

    @property
    def full_address(self):
        bits = [self.address.strip(), self.locality, f"{self.city} {self.pin_code}".strip(), self.district]
        return ", ".join(b for b in bits if b)

    def save(self, *args, **kwargs):
        self.short_code = (self.short_code or "").upper()
        super().save(*args, **kwargs)
        if self.is_head_centre:
            Centre.objects.exclude(pk=self.pk).filter(is_head_centre=True).update(is_head_centre=False)
