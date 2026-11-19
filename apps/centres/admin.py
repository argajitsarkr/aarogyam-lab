from django.contrib import admin

from .models import Centre


@admin.register(Centre)
class CentreAdmin(admin.ModelAdmin):
    """Grouped so the public-site fields read as one job: a centre goes live
    when its photo, hours and phone are in, and `is_public` is the last switch
    rather than the first."""

    list_display = ("name", "short_code", "locality", "is_head_centre", "is_active", "is_public", "public_ready")
    list_filter = ("is_public", "is_active", "district")
    search_fields = ("name", "short_code", "locality", "city")

    fieldsets = (
        (None, {"fields": ("name", "short_code", "colour", "is_head_centre", "is_active", "in_charge")}),
        ("Where it is", {
            "fields": ("address", "locality", "city", "district", "state", "pin_code",
                       "latitude", "longitude", "contact_phone"),
        }),
        ("Public site", {
            "description": (
                "Fill in the photo, the opening hours and the phone number first, then tick "
                "<b>Show on the public site</b>. Anything left blank is hidden rather than "
                "shown empty, and the centre is a 404 until the tick is on."
            ),
            "fields": ("is_public", "public_blurb", "opening_hours", "whatsapp", "photo", "map_url"),
        }),
    )

    @admin.display(description="Public page ready?", boolean=True)
    def public_ready(self, obj):
        """Has this centre got the three things its public page needs? Shown
        whether or not it is live, so the gaps are visible before the switch."""
        return bool(obj.photo and obj.opening_hours and obj.contact_phone)
