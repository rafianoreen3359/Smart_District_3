from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.db.models import Q

MAX_FAILED_ATTEMPTS = 5


class EmailOrUsernameBackend(ModelBackend):
    """Log in with email OR username. Lock the account after 5 wrong passwords."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("email")
        if not login or password is None:
            return None

        User = get_user_model()
        user = User.objects.filter(Q(email__iexact=login) | Q(username__iexact=login)).first()
        if user is None:
            User().set_password(password)  # same timing as a real check
            return None

        if user.is_locked:
            return None  # locked accounts cannot log in, even with the right password

        if user.check_password(password):
            if not self.user_can_authenticate(user):
                return None
            if user.failed_login_attempts:
                User.objects.filter(pk=user.pk).update(failed_login_attempts=0)
                user.failed_login_attempts = 0
            return user

        self._register_failure(user)
        return None

    @staticmethod
    def _register_failure(user):
        attempts = user.failed_login_attempts + 1
        get_user_model().objects.filter(pk=user.pk).update(
            failed_login_attempts=attempts,
            is_locked=attempts >= MAX_FAILED_ATTEMPTS,
        )


class ObjectPermissionBackend(BaseBackend):
    """Object-level rule: only the owner, or a Reviewer, may change a document.

    The user must also hold the normal model permission `change_document`
    (so a Viewer can never edit, even their own document).
    """

    def authenticate(self, request, **kwargs):
        return None  # this backend only handles permissions

    def has_perm(self, user_obj, perm, obj=None):
        if obj is None or not user_obj.is_active or not user_obj.is_authenticated:
            return False
        if perm != "documents.change_document":
            return False
        if not user_obj.has_perm(perm):  # model-level check (obj=None path)
            return False
        return obj.owner_id == user_obj.pk or user_obj.role == "reviewer"
