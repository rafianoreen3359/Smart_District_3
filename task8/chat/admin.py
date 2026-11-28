from django.contrib import admin, messages

from .models import Announcement, Message, Room


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("room", "user", "short_content", "created_at")
    list_filter = ("room",)
    search_fields = ("content", "user__username")

    @admin.display(description="Message")
    def short_content(self, obj):
        return obj.content[:60]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "created_at")
    readonly_fields = ("created_by", "created_at")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if not change:
            self.message_user(request, "Announcement sent to every room.", messages.SUCCESS)
