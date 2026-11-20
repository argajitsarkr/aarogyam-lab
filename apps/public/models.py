"""Content and enquiries for the public site.

The public site is a shop window, not a shop: there is no cart, no payment and
no patient login. Everything a visitor can do ends in an `Enquiry` that the
staff pick up from /staff/enquiries/ and act on by phone, which is how the lab
already works.
"""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage
from apps.core.validators import validate_indian_phone


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_active=True)


class Doctor(TimeStampedModel):
    """A doctor affiliated with one or more centres. Shown on /doctors/ and on
    each centre page. Nothing here is patient data - it is all public by
    definition, so there is no centre scoping."""

    full_name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    qualifications = models.CharField(max_length=160, blank=True, help_text="e.g. MBBS, MD (Pathology)")
    specialty = models.CharField(max_length=120, blank=True)
    registration_no = models.CharField(
        max_length=60, blank=True, help_text="State medical council registration. Shown on the public page."
    )
    centres = models.ManyToManyField("centres.Centre", blank=True, related_name="doctors")
    photo = models.ImageField(upload_to="doctors/", blank=True)
    bio = models.TextField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "full_name"]
        # The staff app already has a `patients.Doctor` (referring doctors), so
        # without this the admin index lists "Doctors" twice.
        verbose_name = "doctor (public site)"
        verbose_name_plural = "doctors (public site)"

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.full_name)[:140]
        super().save(*args, **kwargs)

    @property
    def credential_line(self):
        return " · ".join(p for p in (self.qualifications, self.specialty) if p)


class HealthConcern(TimeStampedModel):
    """A need-based entry point - "Fever", "Diabetes", "Full body" - that maps a
    plain-language worry onto a handful of tests. 1mg's "Shop by health concern"
    tiles are the same idea, and they are how most people arrive."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField(max_length=40, default="science", help_text="Material Symbols ligature name")
    image = models.ImageField(
        upload_to="concerns/", blank=True,
        help_text="A square photo for the tile. With none, the Material Symbols icon above is used instead.",
    )
    blurb = models.CharField(max_length=200, blank=True)
    tests = models.ManyToManyField("patients.TestCatalog", blank=True, related_name="health_concerns")
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:90]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("public:concern", args=[self.slug])


class MedicineCategory(TimeStampedModel):
    """A medicine aisle. The site lists what the pharmacy stocks by category and
    takes the order by phone, WhatsApp or a prescription upload - it does not
    sell online, so there is no product table and no stock count."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField(max_length=40, default="medical_services")
    blurb = models.CharField(max_length=200, blank=True)
    examples = models.TextField(
        blank=True, help_text="One item per line. Indicative only - shown as 'what we usually stock'."
    )
    needs_prescription = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "medicine categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:90]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("public:medicine_category", args=[self.slug])

    @property
    def example_list(self):
        return [line.strip() for line in self.examples.splitlines() if line.strip()]


def prescription_upload_to(instance, filename):
    from django.utils import timezone

    return f"prescriptions/{timezone.now():%Y/%m}/{filename}"


class Enquiry(TimeStampedModel):
    """Everything the public site can produce. One table, because the staff work
    one queue: name, phone, what they want, who called them back."""

    class Kind(models.TextChoices):
        CALLBACK = "CALLBACK", "Call me back"
        TEST = "TEST", "Lab test enquiry"
        PRESCRIPTION = "PRESCRIPTION", "Prescription upload"
        MEDICINE = "MEDICINE", "Medicine enquiry"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        CLOSED = "CLOSED", "Closed"
        SPAM = "SPAM", "Spam"

    kind = models.CharField(max_length=14, choices=Kind.choices, default=Kind.CALLBACK)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=10, validators=[validate_indian_phone])
    centre = models.ForeignKey(
        "centres.Centre", null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries",
        help_text="The centre the visitor chose, if any. Blank means whoever picks it up.",
    )
    test = models.ForeignKey(
        "patients.TestCatalog", null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries"
    )
    message = models.TextField(blank=True)
    # Prescriptions are a medical document, so they go to private_media and are
    # served only through the staff download view - never from a public url.
    prescription = models.FileField(upload_to=prescription_upload_to, storage=private_storage, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries_handled"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    staff_notes = models.TextField(blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.get_kind_display()} - {self.name} ({self.phone})"

    def get_absolute_url(self):
        return reverse("enquiries:detail", args=[self.pk])

    @property
    def is_open(self):
        return self.status in (self.Status.NEW, self.Status.CONTACTED)


class Banner(TimeStampedModel):
    """A slide in the rotating strip under the hero, as 1mg runs across the top
    of their home page.

    The lab changes these far more often than anything else on the site - a camp,
    a seasonal package, a new centre - so they are rows, not template markup.
    An image is optional: with none, the slide renders as its own coloured
    panel with the heading and the button, which is what the lab can produce on
    a Tuesday afternoon without a designer.
    """

    title = models.CharField(max_length=90, help_text="The one line people read. Keep it under about 50 characters.")
    subtitle = models.CharField(max_length=160, blank=True)
    image = models.ImageField(
        upload_to="banners/", blank=True,
        help_text="Wide artwork, about 1200x400. Leave blank for a plain coloured slide.",
    )
    caption_in_image = models.BooleanField(
        default=False,
        verbose_name="The artwork already has the words on it",
        help_text=(
            "Tick this for a finished banner with its own headline. The slide then shows the "
            "artwork alone - no heading, no shading and no button drawn over it. The title is "
            "still used, as the description a screen reader reads out."
        ),
    )
    link_url = models.CharField(
        max_length=300, blank=True,
        help_text="Where the button goes - a path like /lab-tests/ or a full address.",
    )
    link_label = models.CharField(max_length=40, blank=True, default="Know more")
    accent = models.CharField(
        max_length=7, default="#0058B3",
        help_text="Background of a slide that has no image. A hex colour, e.g. #0058B3.",
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, verbose_name="Show on the public site")

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "-created_at"]
        verbose_name = "home page banner"

    def __str__(self):
        return self.title
