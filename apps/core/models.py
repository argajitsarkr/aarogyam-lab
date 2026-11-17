from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Rows are never hard-deleted from the UI; Admins soft-delete instead."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = ActiveQuerySet.as_manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self, user=None):
        self.deleted_at = timezone.now()
        self.deleted_by = user
        if hasattr(self, "is_active"):
            self.is_active = False
        self.save()


class SiteSettings(models.Model):
    """Singleton of business settings editable by Admins."""

    max_active_employees = models.PositiveSmallIntegerField(default=settings.DEFAULT_MAX_ACTIVE_EMPLOYEES)
    retest_lookahead_days = models.PositiveSmallIntegerField(
        default=settings.DEFAULT_RETEST_LOOKAHEAD_DAYS,
        help_text="Re-test candidates are generated when due within this many days (or overdue).",
    )
    price_stale_days = models.PositiveSmallIntegerField(default=settings.PRICE_STALE_DAYS)
    lab_display_name = models.CharField(max_length=100, default="Aarogyam Pathology")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete("site_settings")

    @classmethod
    def load(cls):
        obj = cache.get("site_settings")
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set("site_settings", obj, 300)
        return obj


class SavedFilter(TimeStampedModel):
    """A named combination of list filters a user can pin to the sidebar."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_filters")
    page = models.CharField(max_length=50, help_text="URL name of the list page, e.g. patients:list")
    name = models.CharField(max_length=80)
    querystring = models.CharField(max_length=1000, blank=True)
    pinned = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("user", "page", "name")]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse

        url = reverse(self.page)
        return f"{url}?{self.querystring}" if self.querystring else url
