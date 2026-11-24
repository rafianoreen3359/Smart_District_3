from django.db.models import Q
from django.views.generic import TemplateView
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from documents.models import Document

from .models import APIKey
from .permissions import (
    CanCreateDocument,
    HasValidAPIKeyScope,
    IsAdmin,
    IsAuthenticatedUser,
    IsOwner,
    IsReviewer,
    OwnerOrReviewer,
)
from .serializers import DocumentSerializer, RoleTokenObtainPairSerializer


class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer


class ConsoleView(TemplateView):
    template_name = "api/console.html"


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer

    # ---------- who may do what, per action ----------
    def get_permissions(self):
        permissions = [IsAuthenticatedUser(), HasValidAPIKeyScope()]

        if self.action in ("list", "retrieve"):
            pass  # any authenticated user (or read-scoped API key)
        elif self.action == "create":
            permissions.append(CanCreateDocument())
        elif self.action in ("update", "partial_update"):
            permissions.append(OwnerOrReviewer(IsOwner(), IsReviewer()))  # IsOwner | IsReviewer
        elif self.action == "destroy":
            permissions.append(IsAdmin())
        elif self.action in ("publish", "archive"):
            permissions.append(IsReviewer())
        else:
            permissions.append(IsAdmin())  # anything unexpected is locked down
        return permissions

    # ---------- which documents a user may see ----------
    def get_queryset(self):
        queryset = Document.objects.select_related("owner")
        request = self.request
        user = request.user

        if isinstance(request.auth, APIKey):
            return queryset.filter(status=Document.Status.PUBLISHED)  # services see published only
        if user.is_staff or user.role == User.Role.REVIEWER:
            return queryset
        if user.role == User.Role.EDITOR:
            return queryset.filter(Q(owner=user) | Q(status=Document.Status.PUBLISHED))
        return queryset.filter(status=Document.Status.PUBLISHED)  # viewers

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    # ---------- extra actions ----------
    def _change_status(self, new_status, allowed_from, verb):
        document = self.get_object()
        if document.status not in allowed_from:
            return Response(
                {"detail": f"Cannot {verb} a document that is {document.get_status_display().lower()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        document.status = new_status
        document.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        return self._change_status(Document.Status.PUBLISHED, (Document.Status.DRAFT,), "publish")

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return self._change_status(
            Document.Status.ARCHIVED, (Document.Status.DRAFT, Document.Status.PUBLISHED), "archive"
        )
