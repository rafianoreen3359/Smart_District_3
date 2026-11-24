from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.html import format_html

from .forms import AdminUserCreationForm
from .models import User


class AdminUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label="Password",
        help_text=format_html('Raw passwords are not stored. <a href="{}">Change the password</a>.', "../password/"),
    )

    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    list_display = ("email", "username", "role", "is_active", "is_locked", "failed_login_attempts", "last_login")
    list_filter = ("role", "is_active", "is_locked", "is_staff")
    search_fields = ("email", "username")
    ordering = ("email",)
    filter_horizontal = ("user_permissions",)
    readonly_fields = ("last_login", "date_joined")
    actions = ["unlock_accounts"]

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Role (sets the group automatically)", {"fields": ("role",)}),
        ("Security", {"fields": ("is_locked", "failed_login_attempts")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "role", "password1", "password2")}),
    )

    @admin.action(description="Unlock selected accounts")
    def unlock_accounts(self, request, queryset):
        count = queryset.update(is_locked=False, failed_login_attempts=0)
        self.message_user(request, f"Unlocked {count} account(s).")
