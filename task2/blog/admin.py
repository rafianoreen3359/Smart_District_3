from django.contrib import admin, messages

from .models import Comment, Post


class DeletedFilter(admin.SimpleListFilter):
    title = "deletion status"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return [("no", "Active"), ("yes", "Deleted")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_deleted=True)
        if self.value() == "no":
            return queryset.filter(is_deleted=False)
        return queryset


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "status", "is_deleted", "deleted_at")
    list_filter = (DeletedFilter, "status")
    actions = ["restore_selected"]

    def get_queryset(self, request):
        qs = Post.all_objects.all()
        ordering = self.get_ordering(request)
        return qs.order_by(*ordering) if ordering else qs

    @admin.action(description="Restore selected")
    def restore_selected(self, request, queryset):
        count = queryset.filter(is_deleted=True).restore()
        self.message_user(request, f"Restored {count} post(s).", messages.SUCCESS)


admin.site.register(Comment)