from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, decorators, response
from rest_framework.exceptions import PermissionDenied
from core.permissions import (IsProjectParticipant, IsAssigneeForUpdate,
                              IsProjectOwnerOrAdmin, DenyAPIKeyWrites)
from .models import Task
from .serializers import TaskSerializer

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    filterset_fields = ["project", "status", "assignee"]
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "position", "created_at"]

    def get_queryset(self):
        u = self.request.user
        qs = Task.objects.select_related("project", "assignee")
        if getattr(u, "role", None) == "Integration":
            return qs
        return qs.for_user(u)

    def get_permissions(self):
        base = [DenyAPIKeyWrites, IsProjectParticipant]
        if self.action in ("update", "partial_update"):
            return [c() for c in base] + [(IsAssigneeForUpdate | IsProjectOwnerOrAdmin)()]
        if self.action in ("create", "destroy"):
            return [c() for c in base] + [IsProjectOwnerOrAdmin()]
        return [c() for c in base]

    @extend_schema(responses=TaskSerializer(many=True))
    @decorators.action(detail=False, methods=["get"])
    def overdue(self, request):
        return response.Response(self.get_serializer(self.get_queryset().overdue(), many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("hours", int, description="Window in hours (default 48)")],
        responses=TaskSerializer(many=True),
    )
    @decorators.action(detail=False, methods=["get"], url_path="due-soon")
    def due_soon(self, request):
        hours = int(request.query_params.get("hours", 48))
        return response.Response(self.get_serializer(self.get_queryset().due_soon(hours), many=True).data)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        if not self.request.user.has_perm("projects.change_project", project):
            raise PermissionDenied("Only the project owner or an admin can add tasks.")
        serializer.save()