from datetime import timedelta
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

class TaskQuerySet(models.QuerySet):
    def open(self):
        return self.exclude(status=Task.Status.DONE)

    def overdue(self):
        return self.open().filter(due_date__lt=timezone.now())

    def due_soon(self, hours=48):
        now = timezone.now()
        return self.open().filter(due_date__gte=now, due_date__lte=now + timedelta(hours=hours))

    def for_user(self, user):
        if user.role == "Admin":
            return self
        return self.filter(
            Q(assignee=user) | Q(project__memberships__user=user) | Q(project__owner=user)
        ).distinct()

class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        DOING = "doing", "In progress"
        REVIEW = "review", "Review"
        DONE = "done", "Done"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    position = models.PositiveIntegerField(default=0)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="assigned_tasks")
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TaskQuerySet.as_manager()

# usage: Task.objects.for_user(u).overdue().filter(project=p)