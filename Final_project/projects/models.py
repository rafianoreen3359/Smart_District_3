from django.conf import settings
from django.db import models
from django.utils import timezone

class ProjectQuerySet(models.QuerySet):
    def alive(self):   return self.filter(deleted_at__isnull=True)
    def deleted(self): return self.filter(deleted_at__isnull=False)

class ProjectManager(models.Manager.from_queryset(ProjectQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_projects")
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ProjectManager()          # hides deleted
    all_objects = ProjectQuerySet.as_manager()  # includes deleted

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        super().delete()

class Membership(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    class Meta:
        unique_together = ("project", "user")