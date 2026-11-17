from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Competitor(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    website = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class CompetitorPrice(TimeStampedModel):
    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        PRICE_LIST = "price list", "Price list"
        PHONE = "phone enquiry", "Phone enquiry"
        OTHER = "other", "Other"

    test = models.ForeignKey("patients.TestCatalog", on_delete=models.CASCADE, related_name="competitor_prices")
    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name="prices")
    price = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    source_note = models.CharField(max_length=120, blank=True, help_text="e.g. website, price list, phone enquiry")
    last_verified_on = models.DateField(default=timezone.localdate)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        unique_together = [("test", "competitor")]
        ordering = ["test__name", "competitor__display_order"]

    def __str__(self):
        return f"{self.competitor} — {self.test.name}: ₹{self.price}"

    def is_stale(self, stale_days=None):
        stale_days = stale_days or settings.PRICE_STALE_DAYS
        return (timezone.localdate() - self.last_verified_on).days > stale_days
