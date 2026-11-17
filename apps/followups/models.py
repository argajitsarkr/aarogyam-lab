from django.conf import settings
from django.db import models
import datetime as dt

from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.scoping import CentreScopedQuerySet


class FollowUpQuerySet(CentreScopedQuerySet):
    def open(self):
        return self.filter(status__in=FollowUp.OPEN_STATUSES)

    def due_today(self):
        return self.open().filter(due_date=timezone.localdate())

    def overdue(self):
        return self.open().filter(due_date__lt=timezone.localdate())

    def upcoming(self, days=7):
        today = timezone.localdate()
        return self.open().filter(due_date__gt=today, due_date__lte=today + dt.timedelta(days=days))


class FollowUp(TimeStampedModel):
    class Reason(models.TextChoices):
        DOCTOR_REFERRAL = "DOCTOR_REFERRAL", "Doctor referral"
        RE_TEST = "RE_TEST", "Re-test"
        ABNORMAL_RESULT = "ABNORMAL_RESULT", "Abnormal result"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        HIGH = "HIGH", "High"
        MEDIUM = "MEDIUM", "Medium"
        LOW = "LOW", "Low"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONTACTED = "CONTACTED", "Contacted"
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        NOT_INTERESTED = "NOT_INTERESTED", "Not Interested"
        UNREACHABLE = "UNREACHABLE", "Unreachable"

    OPEN_STATUSES = (Status.PENDING, Status.CONTACTED, Status.SCHEDULED)
    KANBAN_COLUMNS = (Status.PENDING, Status.CONTACTED, Status.SCHEDULED, Status.COMPLETED)

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="followups")
    centre = models.ForeignKey("centres.Centre", on_delete=models.PROTECT, related_name="followups")
    source_visit = models.ForeignKey("patients.Visit", null=True, blank=True, on_delete=models.SET_NULL, related_name="followups")
    source_test = models.ForeignKey("patients.VisitTest", null=True, blank=True, on_delete=models.SET_NULL, related_name="followups")
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.OTHER)
    referring_doctor = models.ForeignKey("patients.Doctor", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    due_date = models.DateField(default=timezone.localdate, db_index=True)
    priority = models.CharField(max_length=6, choices=Priority.choices, default=Priority.MEDIUM)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_followups")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)
    next_action_date = models.DateField(null=True, blank=True)
    scheduled_date = models.DateField(null=True, blank=True, help_text="Appointment date when status is Scheduled.")
    scheduled_centre = models.ForeignKey("centres.Centre", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completed_visit = models.ForeignKey("patients.Visit", null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_followups")
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    objects = FollowUpQuerySet.as_manager()

    class Meta:
        ordering = ["due_date", "-priority"]

    def __str__(self):
        return f"{self.get_reason_display()} — {self.patient.full_name} (due {self.due_date:%d-%m-%Y})"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue(self):
        return self.is_open and self.due_date < timezone.localdate()

    @property
    def calendar_date(self):
        return self.scheduled_date if self.status == self.Status.SCHEDULED and self.scheduled_date else self.due_date


class ContactNote(TimeStampedModel):
    """Contact history entry for a follow-up (each call/visit/message)."""

    followup = models.ForeignKey(FollowUp, on_delete=models.CASCADE, related_name="contact_notes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    status_from = models.CharField(max_length=15, blank=True)
    status_to = models.CharField(max_length=15, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
