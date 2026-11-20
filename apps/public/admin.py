"""Admin for the public site's content.

This is where the lab edits the public site: doctors, health concerns, medicine
aisles. The enquiry queue is deliberately NOT editable here - it has its own
staff page at /staff/enquiries/, which records who handled each one. It is
registered read-only so an Admin can still look at an old enquiry.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Banner, Doctor, Enquiry, HealthConcern, MedicineCategory, Review


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
            "fields": ("image", "caption_in_image", "accent"),
        }),
        ("Button", {
            "description": "Ignored when the artwork already carries its own words - the whole slide is the link.",
            "fields": ("link_url", "link_label"),
        }),
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
    list_display = ("name", "icon", "has_image", "test_count", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "blurb")
    filter_horizontal = ("tests",)
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "slug", "icon", "image", "blurb", "tests", "display_order", "is_active")

    @admin.display(description="Photo?", boolean=True)
    def has_image(self, obj):
        return bool(obj.image)

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


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Customer ratings from the QR code. Instant-publish by default; untick
    'shown on the public site' to hide a bad one, or use the bulk actions."""

    list_display = ("created_at", "name", "rating", "centre", "is_published", "short_comment")
    list_editable = ("is_published",)
    list_filter = ("is_published", "rating", "centre")
    search_fields = ("name", "comment")
    date_hierarchy = "created_at"
    readonly_fields = ("client_ip", "created_at", "updated_at")
    actions = ("publish", "hide")

    @admin.display(description="comment")
    def short_comment(self, obj):
        return (obj.comment[:60] + "...") if len(obj.comment) > 60 else obj.comment

    @admin.action(description="Publish selected reviews")
    def publish(self, request, queryset):
        queryset.update(is_published=True)
        self._clear_cache()

    @admin.action(description="Hide selected reviews")
    def hide(self, request, queryset):
        queryset.update(is_published=False)
        self._clear_cache()

    def _clear_cache(self):
        from django.core.cache import cache

        cache.delete_many(["reviews:summary:all"])

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        from .stats import clear_rating_cache

        clear_rating_cache(obj.centre_id)


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
