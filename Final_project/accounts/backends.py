from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, email=None, **kw):
        User = get_user_model()
        email = email or username
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            User().set_password(password)  # timing-attack mitigation
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user


class ObjectPermissionBackend:
    """Object-level rules: managers own their projects, members see joined ones."""
    def authenticate(self, request, **kw):
        return None

    def has_perm(self, user, perm, obj=None):
        if obj is None or not user.is_active:
            return False
        if user.role == "Admin":
            return True
        project = getattr(obj, "project", obj)
        action = perm.split(".")[-1].split("_")[0]
        if user.role == "Manager":
            return project.owner_id == user.id
        if user.role == "Member":
            joined = project.memberships.filter(user=user).exists()
            if action == "view":
                return joined
            if action == "change" and hasattr(obj, "assignee_id"):
                return joined and obj.assignee_id == user.id
        return False

    def get_user(self, user_id):
        return None