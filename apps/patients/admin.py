from django.contrib import admin

from .models import Doctor, Patient, PinCodeLocation, TestCatalog, Visit, VisitTest


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "full_name", "phone", "registered_at_centre", "created_at")
    search_fields = ("patient_id", "full_name", "phone")
    list_filter = ("registered_at_centre",)


class VisitTestInline(admin.TabularInline):
    model = VisitTest
    extra = 0


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("patient", "centre", "visit_date")
    list_filter = ("centre",)
    inlines = [VisitTestInline]
    raw_id_fields = ("patient",)


admin.site.register(Doctor)
admin.site.register(TestCatalog)


@admin.register(PinCodeLocation)
class PinCodeLocationAdmin(admin.ModelAdmin):
    list_display = ("pin_code", "label", "latitude", "longitude")
