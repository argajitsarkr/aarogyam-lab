"""Admin for the settings singleton.

`SiteSettings` had no admin at all until the public site needed it. That was
fine while every field was a number with a sensible default; it stopped being
fine the moment the public phone number, the pharmacy licence and the
pharmacist's name lived here, because those have no default and the footer and
callback bar stay hidden until somebody types them in.

It is a singleton (`pk=1`, see `SiteSettings.save`), so adding and deleting are
both off: there is one row, and the changelist goes straight to it.
"""
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Lab", {
            "fields": ("lab_display_name",),
        }),
        ("Public site - contact", {
            "description": (
                "These appear on every public page. Leave a field blank and its button or "
                "line simply does not render - the site never shows a placeholder."
            ),
            "fields": ("public_phone", "public_whatsapp", "public_email", "home_collection_area"),
        }),
        ("Public site - pharmacy compliance", {
            "description": (
                "Required on a site that takes medicine orders. The compliance block in the "
                "footer stays hidden until the licence number or the pharmacist is filled in."
            ),
            "fields": ("pharmacy_licence_no", "pharmacist_name", "pharmacist_reg_no"),
        }),
        ("Public site - claims", {
            "description": "Only write what the lab can stand behind. Blank hides the claim.",
            "fields": ("medicine_discount_note",),
        }),
        ("Internal rules", {
            "classes": ("collapse",),
            "fields": ("max_active_employees", "retest_lookahead_days", "price_stale_days"),
        }),
    )
    readonly_fields = ()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """There is only ever one row, so skip the list and open it."""
        obj = SiteSettings.load()
        return HttpResponseRedirect(reverse("admin:core_sitesettings_change", args=[obj.pk]))
