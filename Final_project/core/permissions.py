from rest_framework import permissions
from accounts.api_auth import APIKeyUser

class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == "Admin"

class IsManagerRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == "Manager"

class IsMemberRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == "Member"

class IsAPIKeyReadOnly(permissions.BasePermission):
    """API keys may only use safe methods."""
    def has_permission(self, request, view):
        return isinstance(request.user, APIKeyUser) and request.method in permissions.SAFE_METHODS

class IsProjectOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        project = getattr(obj, "project", obj)
        return request.user.role == "Admin" or project.owner_id == request.user.id

class IsProjectParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, APIKeyUser):
            return request.method in permissions.SAFE_METHODS
        return request.user.has_perm("projects.view_project", obj)

class IsAssigneeForUpdate(permissions.BasePermission):
    """Members may only modify tasks assigned to them."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(obj, "assignee_id", None) == request.user.id


# Composition with | & ~ (DRF supports operator composition on classes):
IsStaffRole = IsAdminRole | IsManagerRole
CanWriteProject = IsAdminRole | IsManagerRole          # members and keys can't create/edit
CanReadAnything = permissions.IsAuthenticated | IsAPIKeyReadOnly


class DenyAPIKeyWrites(permissions.BasePermission):
    def has_permission(self, request, view):
        return not (isinstance(request.user, APIKeyUser)
                    and request.method not in permissions.SAFE_METHODS)