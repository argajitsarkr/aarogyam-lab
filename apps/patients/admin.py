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


@admin.register(TestCatalog)
class TestCatalogAdmin(admin.ModelAdmin):
    """The catalogue is long, and publishing it to the public site is the one
    job here that runs down the whole list. So: `is_public` is editable from the
    changelist, filterable, and there is a bulk action - but only for taking a
    test OFF the site. Putting one on needs a description, which has to be
    written one at a time, and a bulk "publish" button would quietly produce a
    public page with nothing on it."""

    list_display = ("name", "code", "category", "price", "is_active", "is_public", "public_ready")
    list_editable = ("is_public",)
    list_filter = ("is_public", "is_active", "category", "fasting_required", "needs_clinical_review")
    search_fields = ("name", "code")
    list_per_page = 50
    actions = ["unpublish"]

    fieldsets = (
        (None, {"fields": ("code", "name", "category", "sample_type", "price", "is_active")}),
        ("Re-test rules", {
            "classes": ("collapse",),
            "fields": ("retest_interval_days", "is_chronic_monitoring", "needs_clinical_review"),
        }),
        ("Public site", {
            "description": (
                "Write the description in plain language - no abbreviations - then tick "
                "<b>List on the public site</b>. Until then the test is a 404 on the public "
                "side and does not appear in the sitemap."
            ),
            "fields": ("is_public", "public_description", "fasting_required", "report_in_hours"),
        }),
    )

    @admin.display(description="Description written?", boolean=True)
    def public_ready(self, obj):
        return bool(obj.public_description)

    @admin.display(description="Take off the public site")
    def unpublish(self, request, queryset):
        count = queryset.update(is_public=False)
        self.message_user(request, f"{count} test(s) removed from the public site.")


@admin.register(PinCodeLocation)
class PinCodeLocationAdmin(admin.ModelAdmin):
    list_display = ("pin_code", "label", "latitude", "longitude")
