from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.scoping import CentreScopedQuerySet


class RetestCandidateQuerySet(CentreScopedQuerySet):
    def open(self):
        return self.filter(status__in=RetestCandidate.OPEN_STATUSES)


class RetestCandidate(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONTACTED = "CONTACTED", "Contacted"
        SCHEDULED = "SCHEDULED", "Scheduled"
        CONVERTED = "CONVERTED", "Completed"
        NOT_INTERESTED = "NOT_INTERESTED", "Not Interested"
        CLOSED = "CLOSED", "Closed"

    OPEN_STATUSES = (Status.PENDING, Status.CONTACTED, Status.SCHEDULED)
    KANBAN_COLUMNS = (Status.PENDING, Status.CONTACTED, Status.SCHEDULED, Status.CONVERTED)

    patient = models.ForeignKey("patients.Patient", on_delete=models.CASCADE, related_name="retest_candidates")
    centre = models.ForeignKey("centres.Centre", on_delete=models.PROTECT, related_name="retest_candidates")
    source_test = models.ForeignKey("patients.VisitTest", on_delete=models.CASCADE, related_name="retest_candidates")
    test = models.ForeignKey("patients.TestCatalog", on_delete=models.PROTECT, related_name="+")
    due_date = models.DateField(db_index=True)
    priority_score = models.IntegerField(default=0, db_index=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="retest_candidates")
    callback_date = models.DateField(null=True, blank=True)
    booked_date = models.DateField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_called_at = models.DateTimeField(null=True, blank=True)
    converted_visit = models.ForeignKey("patients.Visit", null=True, blank=True, on_delete=models.SET_NULL, related_name="converted_retests")
    converted_test = models.ForeignKey("patients.VisitTest", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    converted_at = models.DateTimeField(null=True, blank=True)

    objects = RetestCandidateQuerySet.as_manager()

    class Meta:
        ordering = ["-priority_score", "due_date"]
        constraints = [
            models.UniqueConstraint(fields=["source_test"], name="uniq_candidate_per_source_test"),
        ]

    def __str__(self):
        return f"{self.test.name} re-test — {self.patient.full_name}"

    @property
    def days_overdue(self):
        return (timezone.localdate() - self.due_date).days

    @property
    def calendar_date(self):
        if self.status == self.Status.SCHEDULED and self.booked_date:
            return self.booked_date
        if self.status == self.Status.CONTACTED and self.callback_date:
            return self.callback_date
        return self.due_date


class CallLog(models.Model):
    class Outcome(models.TextChoices):
        BOOKED = "BOOKED", "Booked"
        CALL_BACK = "CALL_BACK", "Call Back Later"
        NOT_INTERESTED = "NOT_INTERESTED", "Not Interested"
        WRONG_NUMBER = "WRONG_NUMBER", "Wrong Number"
        NO_ANSWER = "NO_ANSWER", "No Answer"
        DO_NOT_CALL = "DO_NOT_CALL", "Do Not Call"

    # Outcomes where we actually spoke to the patient (denominator of conversion rate)
    CONTACTED_OUTCOMES = (Outcome.BOOKED, Outcome.CALL_BACK, Outcome.NOT_INTERESTED, Outcome.DO_NOT_CALL)

    candidate = models.ForeignKey(RetestCandidate, on_delete=models.CASCADE, related_name="calls")
    centre = models.ForeignKey("centres.Centre", on_delete=models.PROTECT, related_name="+")
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="call_logs")
    called_at = models.DateTimeField(default=timezone.now, db_index=True)
    outcome = models.CharField(max_length=15, choices=Outcome.choices)
    callback_date = models.DateField(null=True, blank=True)
    booked_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    converted = models.BooleanField(default=False, help_text="Set when the booked patient actually returned for the test.")

    class Meta:
        ordering = ["-called_at"]

    def __str__(self):
        return f"{self.get_outcome_display()} — {self.candidate}"
