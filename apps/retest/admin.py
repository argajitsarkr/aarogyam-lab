from django.contrib import admin

from .models import CallLog, RetestCandidate


@admin.register(RetestCandidate)
class RetestCandidateAdmin(admin.ModelAdmin):
    list_display = ("patient", "test", "centre", "due_date", "priority_score", "status")
    list_filter = ("centre", "status")
    raw_id_fields = ("patient", "source_test", "converted_visit", "converted_test")


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = ("candidate", "employee", "called_at", "outcome", "converted")
    list_filter = ("outcome", "centre")
    raw_id_fields = ("candidate",)
