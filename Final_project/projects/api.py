from django.db.models import Count
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import viewsets, decorators, response, status
from core.permissions import (CanWriteProject, IsProjectOwnerOrAdmin,
                              IsProjectParticipant, DenyAPIKeyWrites)
from .models import Project
from .serializers import ProjectSerializer

@extend_schema_view(
    list=extend_schema(summary="List projects visible to the caller"),
    destroy=extend_schema(summary="Soft-delete a project"),
)
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ["owner"]
    search_fields = ["name"]

    def get_queryset(self):
        u = self.request.user
        qs = Project.objects.annotate(task_count=Count("tasks"))
        if getattr(u, "role", None) in ("Admin", "Integration"):
            return qs
        return qs.filter(memberships__user=u).distinct() | qs.filter(owner=u)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "restore"):
            classes = [DenyAPIKeyWrites, CanWriteProject, IsProjectOwnerOrAdmin]
        else:
            classes = [IsProjectParticipant]
        return [c() for c in classes]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @decorators.action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        project = Project.all_objects.get(pk=pk)
        self.check_object_permissions(request, project)
        project.restore()
        return response.Response(self.get_serializer(project).data)