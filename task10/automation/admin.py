from django.contrib import admin

from .models import DigestPreference, ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("base", "quote", "rate", "fetched_at")


@admin.register(DigestPreference)
class DigestPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "send_time", "enabled", "updated_at")
    readonly_fields = ("periodic_task",)
