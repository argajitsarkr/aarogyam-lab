from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "role", "home_centre", "phone", "is_active")
    list_filter = ("role", "home_centre", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Lab", {"fields": ("role", "phone", "home_centre", "extra_centres", "must_change_password")}),
    )
