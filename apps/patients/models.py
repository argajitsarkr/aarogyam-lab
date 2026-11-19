from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.centres.models import DISTRICT_CHOICES
from apps.core.models import ActiveQuerySet, SoftDeleteModel, TimeStampedModel
from apps.core.validators import normalize_phone, validate_indian_phone, validate_pin_code


# --------------------------------------------------------------------------
# Patient
# --------------------------------------------------------------------------
class PatientIdSequence(models.Model):
    centre = models.ForeignKey("centres.Centre", on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("centre", "year")]


def next_patient_id(centre):
    """Atomically allocate e.g. ARP-2026-000123 (per centre, per year)."""
    year = timezone.localdate().year
    with transaction.atomic():
        seq, _ = PatientIdSequence.objects.select_for_update().get_or_create(centre=centre, year=year)
        seq.last_number += 1
        seq.save(update_fields=["last_number"])
    return f"{centre.short_code}-{year}-{seq.last_number:06d}"


class PatientQuerySet(ActiveQuerySet):
    def visible_in_centres(self, centre_ids):
        """Patients registered at, or who have visited, any of these centres."""
        visited = Visit.objects.filter(patient=OuterRef("pk"), centre_id__in=centre_ids, deleted_at__isnull=True)
        return self.filter(Q(registered_at_centre_id__in=centre_ids) | Exists(visited))

    def contactable(self):
        return self.filter(consent_to_contact=True, do_not_call=False, deleted_at__isnull=True)


class Patient(TimeStampedModel, SoftDeleteModel):
    class Sex(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    patient_id = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=150, db_index=True)
    age_years = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Age (years)")
    dob = models.DateField(null=True, blank=True, verbose_name="Date of birth")
    sex = models.CharField(max_length=1, choices=Sex.choices, blank=True)
    phone = models.CharField(max_length=10, db_index=True, blank=True, validators=[validate_indian_phone])
    alt_phone = models.CharField(max_length=10, blank=True, validators=[validate_indian_phone], verbose_name="Alternate phone")
    email = models.EmailField(blank=True)

    house_street = models.CharField(max_length=200, blank=True, verbose_name="House / street")
    locality = models.CharField(max_length=120, blank=True, db_index=True, verbose_name="Locality / area")
    village_ward = models.CharField(max_length=120, blank=True, verbose_name="Village / ward")
    city = models.CharField(max_length=80, blank=True, default="Agartala")
    district = models.CharField(max_length=40, choices=DISTRICT_CHOICES, default="West Tripura")
    state = models.CharField(max_length=60, default="Tripura")
    pin_code = models.CharField(max_length=6, blank=True, db_index=True, validators=[validate_pin_code])

    registered_at_centre = models.ForeignKey("centres.Centre", on_delete=models.PROTECT, related_name="patients_registered")
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    consent_to_contact = models.BooleanField(
        default=False, help_text="Patient agreed to be contacted for follow-ups and re-test reminders."
    )
    consent_at = models.DateTimeField(null=True, blank=True)
    do_not_call = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    objects = PatientQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.patient_id})"

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone) or ""
        self.alt_phone = normalize_phone(self.alt_phone) or ""
        if self.consent_to_contact and not self.consent_at:
            self.consent_at = timezone.now()
        if not self.consent_to_contact:
            self.consent_at = None
        if not self.patient_id:
            self.patient_id = next_patient_id(self.registered_at_centre)
        super().save(*args, **kwargs)

    @property
    def age_display(self):
        if self.dob:
            today = timezone.localdate()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return self.age_years

    @property
    def last_visit(self):
        return self.visits.filter(deleted_at__isnull=True).select_related("centre").order_by("-visit_date", "-pk").first()

    @property
    def is_contactable(self):
        return self.consent_to_contact and not self.do_not_call


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------
class Doctor(TimeStampedModel):
    name = models.CharField(max_length=120)
    clinic = models.CharField(max_length=150, blank=True, verbose_name="Clinic / hospital")
    phone = models.CharField(max_length=10, blank=True, validators=[validate_indian_phone])
    specialty = models.CharField(max_length=80, blank=True)
    locality = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"Dr {self.name}" + (f" — {self.clinic}" if self.clinic else "")


class TestCatalog(TimeStampedModel):
    __test__ = False  # stop pytest treating the model as a test class

    class Category(models.TextChoices):
        HAEMATOLOGY = "HAEMATOLOGY", "Haematology"
        BIOCHEMISTRY = "BIOCHEMISTRY", "Biochemistry"
        HORMONES = "HORMONES", "Hormones"
        SEROLOGY = "SEROLOGY", "Serology"
        IMMUNOLOGY = "IMMUNOLOGY", "Immunology"
        MICROBIOLOGY = "MICROBIOLOGY", "Microbiology"
        CLINICAL_PATHOLOGY = "CLINICAL_PATHOLOGY", "Clinical Pathology"
        VITAMINS = "VITAMINS", "Vitamins & Minerals"
        CARDIAC = "CARDIAC", "Cardiac"
        PROFILE = "PROFILE", "Profiles / Packages"
        OTHER = "OTHER", "Other"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150, db_index=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.BIOCHEMISTRY)
    sample_type = models.CharField(max_length=60, blank=True)
    price = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Our price (₹)")
    retest_interval_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Recommended re-test interval. Blank = never suggest a re-test."
    )
    is_chronic_monitoring = models.BooleanField(default=False)
    needs_clinical_review = models.BooleanField(default=True, help_text="Seeded interval pending review by the pathologist.")
    is_active = models.BooleanField(default=True)

    # ---- public site ------------------------------------------------------
    is_public = models.BooleanField(
        default=False, verbose_name="List on the public site",
        help_text="Off by default: a test is only listed once its description reads plainly to a patient.",
    )
    public_description = models.TextField(blank=True, help_text="Plain language, no abbreviations. Two or three sentences.")
    fasting_required = models.BooleanField(default=False)
    report_in_hours = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Typical turnaround, shown as 'Report in 24 hours'."
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "test"

    def __str__(self):
        return f"{self.name} ({self.code})"


class PinCodeLocation(models.Model):
    """Approximate centroid per PIN code, used only for the aggregated density map."""

    pin_code = models.CharField(max_length=6, primary_key=True, validators=[validate_pin_code])
    label = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return self.pin_code


# --------------------------------------------------------------------------
# Visits
# --------------------------------------------------------------------------
def report_upload_to(instance, filename):
    """Kept only so the historical migration 0001_initial still imports. Report PDF
    upload/download was removed; nothing calls this."""
    return f"reports/{instance.pk}/{filename}"


class VisitQuerySet(ActiveQuerySet):
    pass


class Visit(TimeStampedModel, SoftDeleteModel):
    class CollectionType(models.TextChoices):
        CENTRE = "CENTRE", "At Centre"
        HOME = "HOME", "Home Collection"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="visits")
    centre = models.ForeignKey("centres.Centre", on_delete=models.PROTECT, related_name="visits")
    visit_date = models.DateField(default=timezone.localdate, db_index=True)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    referring_doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.SET_NULL, related_name="visits")
    sample_collection_type = models.CharField(max_length=6, choices=CollectionType.choices, default=CollectionType.CENTRE)
    collection_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    objects = VisitQuerySet.as_manager()

    class Meta:
        ordering = ["-visit_date", "-pk"]

    def __str__(self):
        return f"Visit {self.visit_date:%d-%m-%Y} — {self.patient.full_name} @ {self.centre.short_code}"


class VisitTest(TimeStampedModel):
    class ResultStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        REPORTED = "REPORTED", "Reported"

    class Flag(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        BORDERLINE = "BORDERLINE", "Borderline"
        ABNORMAL = "ABNORMAL", "Abnormal"

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="tests")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="visit_tests", editable=False)
    test = models.ForeignKey(TestCatalog, on_delete=models.PROTECT, related_name="visit_tests")
    result_status = models.CharField(max_length=8, choices=ResultStatus.choices, default=ResultStatus.PENDING)
    result_summary = models.CharField(max_length=255, blank=True)
    flag = models.CharField(max_length=10, choices=Flag.choices, blank=True)
    report_date = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["visit", "test__name"]
        indexes = [models.Index(fields=["patient", "test"])]

    def __str__(self):
        return f"{self.test.name} — {self.visit}"

    def save(self, *args, **kwargs):
        self.patient_id = self.visit.patient_id
        if self.result_status == self.ResultStatus.REPORTED and not self.report_date:
            self.report_date = timezone.localdate()
        super().save(*args, **kwargs)
