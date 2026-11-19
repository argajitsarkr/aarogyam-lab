"""Admin for the public site's content.

This is where the lab edits the public site: doctors, health concerns, medicine
aisles. The enquiry queue is deliberately NOT editable here - it has its own
staff page at /staff/enquiries/, which records who handled each one. It is
registered read-only so an Admin can still look at an old enquiry.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Banner, Doctor, Enquiry, HealthConcern, MedicineCategory


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """The rotating strip on the home page. Lowest display order shows first."""

    list_display = ("title", "has_image", "link_url", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("title", "subtitle")
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "display_order", "is_active")}),
        ("Artwork", {
            "description": (
                "Leave the image blank and the slide is drawn as a plain coloured panel "
                "with the words on it - still a usable slide, never a broken one."
            ),
            "fields": ("image", "accent"),
        }),
        ("Button", {"fields": ("link_url", "link_label")}),
    )

    @admin.display(description="Artwork?", boolean=True)
    def has_image(self, obj):
        return bool(obj.image)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "qualifications", "specialty", "registration_no", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active", "centres")
    search_fields = ("full_name", "qualifications", "specialty", "registration_no")
    filter_horizontal = ("centres",)
    prepopulated_fields = {"slug": ("full_name",)}


@admin.register(HealthConcern)
class HealthConcernAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "test_count", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "blurb")
    filter_horizontal = ("tests",)
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="tests")
    def test_count(self, obj):
        return obj.tests.count()


@admin.register(MedicineCategory)
class MedicineCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "needs_prescription", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active", "needs_prescription")
    search_fields = ("name", "blurb", "examples")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    """Read-only: enquiries are worked at /staff/enquiries/, which stamps who
    handled each one. Editing here would bypass that record."""

    list_display = ("created_at", "kind", "name", "phone", "centre", "status", "handled_by")
    list_filter = ("status", "kind", "centre")
    search_fields = ("name", "phone", "message")
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in Enquiry._meta.fields] + ["queue_link"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Work this enquiry")
    def queue_link(self, obj):
        if not obj.pk:
            return "-"
        return format_html('<a href="{}">Open in the enquiry queue</a>', obj.get_absolute_url())
