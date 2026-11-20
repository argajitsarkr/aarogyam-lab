from django.contrib import admin

from .models import Competitor, CompetitorPrice


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("name", "has_logo", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    fields = ("name", "logo", "website", "display_order", "is_active")

    @admin.display(boolean=True, description="Logo")
    def has_logo(self, obj):
        return bool(obj.logo)


@admin.register(CompetitorPrice)
class CompetitorPriceAdmin(admin.ModelAdmin):
    list_display = ("test", "competitor", "price", "last_verified_on")
    list_filter = ("competitor",)
