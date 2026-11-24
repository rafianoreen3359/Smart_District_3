from django.contrib import admin, messages
from django.utils.html import format_html

from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "owner", "scopes", "active", "created_at", "last_used_at", "revoked_at")
    fields = ("name", "owner", "scopes", "prefix", "key_hash", "created_at", "last_used_at", "revoked_at")
    readonly_fields = ("prefix", "key_hash", "created_at", "last_used_at", "revoked_at")
    actions = ["revoke_keys"]

    @admin.display(boolean=True, description="Active")
    def active(self, obj):
        return obj.is_active

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)
            return
        raw = APIKey.generate_raw()
        obj.set_key(raw)
        super().save_model(request, obj, form, change)
        messages.warning(
            request,
            format_html(
                "New API key for <b>{}</b>. Copy it now, it is never shown again: <code>{}</code>", obj.name, raw
            ),
        )

    @admin.action(description="Revoke selected keys")
    def revoke_keys(self, request, queryset):
        count = 0
        for key in queryset:
            if key.is_active:
                key.revoke()
                count += 1
        self.message_user(request, f"Revoked {count} key(s).")
