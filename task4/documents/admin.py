from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("title", "owner__email", "owner__username")
