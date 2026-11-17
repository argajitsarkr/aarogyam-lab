from django.contrib import admin

from .models import ContactNote, FollowUp


class ContactNoteInline(admin.TabularInline):
    model = ContactNote
    extra = 0


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("patient", "centre", "reason", "due_date", "status", "assigned_to")
    list_filter = ("centre", "status", "reason")
    raw_id_fields = ("patient", "source_visit", "source_test", "completed_visit")
    inlines = [ContactNoteInline]
