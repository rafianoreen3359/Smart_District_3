from django.utils import timezone
from rest_framework import serializers
from .models import Task

class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ["id", "project", "title", "description", "status", "position",
                  "assignee", "due_date", "is_overdue", "created_at"]
        read_only_fields = ["created_at"]

    def get_is_overdue(self, obj) -> bool:
        return bool(obj.due_date and obj.status != Task.Status.DONE and obj.due_date < timezone.now())

    def validate_due_date(self, value):
        if value and self.instance is None and value < timezone.now():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        assignee = attrs.get("assignee")
        if assignee and project and not (
            project.memberships.filter(user=assignee).exists() or project.owner_id == assignee.id
        ):
            raise serializers.ValidationError({"assignee": "Assignee must be a project member."})
        return attrs