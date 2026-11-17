from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.validators import normalize_phone, validate_indian_phone


class UserQuerySet(models.QuerySet):
    def active_admins(self):
        return self.filter(role=User.Role.ADMIN, is_active=True, deleted_at__isnull=True)

    def active_employees(self):
        return self.filter(role=User.Role.EMPLOYEE, is_active=True, deleted_at__isnull=True)


class AppUserManager(UserManager.from_queryset(UserQuerySet)):

    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("must_change_password", False)
        return super().create_superuser(username, email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        EMPLOYEE = "EMPLOYEE", "Centre Employee"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True, validators=[validate_indian_phone])
    home_centre = models.ForeignKey(
        "centres.Centre", null=True, blank=True, on_delete=models.PROTECT, related_name="employees",
        help_text="Required for employees. New patients and visits are tagged to this centre.",
    )
    extra_centres = models.ManyToManyField(
        "centres.Centre", blank=True, related_name="granted_users",
        help_text="Optional read access to other centres' full patient records.",
    )
    must_change_password = models.BooleanField(default=True)
    ui_preferences = models.JSONField(default=dict, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AppUserManager()

    class Meta:
        ordering = ["first_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    # ---- roles & scope ---------------------------------------------------
    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    def accessible_centre_ids(self):
        """Centres whose full records this user may open."""
        if hasattr(self, "_accessible_ids"):
            return self._accessible_ids
        from apps.centres.models import Centre

        if self.is_admin:
            ids = set(Centre.objects.values_list("pk", flat=True))
        else:
            ids = set(self.extra_centres.values_list("pk", flat=True))
            if self.home_centre_id:
                ids.add(self.home_centre_id)
        self._accessible_ids = ids
        return ids

    # ---- validation (caps enforced at model level) -------------------------
    def clean(self):
        super().clean()
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.role == self.Role.EMPLOYEE and not self.home_centre_id:
            raise ValidationError({"home_centre": "Employees must have a home centre."})
        self.validate_caps()

    def validate_caps(self):
        from apps.core.models import SiteSettings

        if not self.is_active or self.deleted_at:
            return
        others = User.objects.exclude(pk=self.pk) if self.pk else User.objects.all()
        if self.role == self.Role.ADMIN:
            cap = settings.MAX_ACTIVE_ADMINS
            if others.active_admins().count() >= cap:
                raise ValidationError(f"There can be at most {cap} active Admins. Deactivate one first.")
        else:
            cap = SiteSettings.load().max_active_employees
            if others.active_employees().count() >= cap:
                raise ValidationError(
                    f"The active employee limit ({cap}) has been reached. Deactivate an employee "
                    f"or ask an Admin to raise the cap in Settings."
                )

    def save(self, *args, **kwargs):
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.role == self.Role.EMPLOYEE:
            self.is_staff = False
            self.is_superuser = False
        self.validate_caps()
        super().save(*args, **kwargs)
        self.__dict__.pop("_accessible_ids", None)

    def soft_delete(self, by=None):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save()
