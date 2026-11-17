from django.contrib import admin

from .models import Competitor, CompetitorPrice


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("name", "display_order", "is_active")


@admin.register(CompetitorPrice)
class CompetitorPriceAdmin(admin.ModelAdmin):
    list_display = ("test", "competitor", "price", "last_verified_on")
    list_filter = ("competitor",)
