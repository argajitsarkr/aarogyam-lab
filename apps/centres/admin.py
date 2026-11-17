from django.contrib import admin

from .models import Centre


@admin.register(Centre)
class CentreAdmin(admin.ModelAdmin):
    list_display = ("name", "short_code", "locality", "is_head_centre", "is_active")
