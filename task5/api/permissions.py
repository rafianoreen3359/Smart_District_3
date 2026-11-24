from rest_framework.permissions import OR, SAFE_METHODS, BasePermission

from .models import APIKey


class IsAuthenticatedUser(BasePermission):
    message = "Authentication credentials were not provided or are not valid."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsOwner(BasePermission):
    """Object-level: the document belongs to the requesting user."""

    message = "Only the owner of this document can do that."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.pk


class IsReviewer(BasePermission):
    """Reviewers (and superusers) only."""

    message = "Only Reviewers can do that."

    def _is_reviewer(self, request):
        user = request.user
        return bool(user and user.is_authenticated and (user.role == "reviewer" or user.is_superuser))

    def has_permission(self, request, view):
        return self._is_reviewer(request)

    def has_object_permission(self, request, view, obj):
        return self._is_reviewer(request)


class IsAdmin(BasePermission):
    """Admin (staff) users only. Used for deleting."""

    message = "Only administrators can delete documents."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class CanCreateDocument(BasePermission):
    """Uses the Django model permission from the Day 4 groups (Editors have it)."""

    message = "Your role is not allowed to create documents."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_perm("documents.add_document"))


class HasValidAPIKeyScope(BasePermission):
    """Applies only to API-key requests. Keys are read-only and need the read scope."""

    message = "This API key is not allowed to perform this action."
    required_scope = APIKey.READ_SCOPE

    def has_permission(self, request, view):
        key = request.auth
        if not isinstance(key, APIKey):
            return True  # a JWT user: this permission does not apply
        if request.method not in SAFE_METHODS:
            self.message = "API keys are read-only. Use a user token to modify documents."
            return False
        if not key.is_usable:
            self.message = "This API key is no longer active."
            return False
        if not key.has_scope(self.required_scope):
            self.message = f"This API key lacks the required scope: {self.required_scope}."
            return False
        return True


class OwnerOrReviewer(OR):
    """IsOwner | IsReviewer, with one clear 403 message for the combination."""

    message = "Only the document's owner or a Reviewer can edit it."
