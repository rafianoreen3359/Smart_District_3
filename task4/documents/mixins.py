from django.contrib.auth.mixins import AccessMixin


class OwnerOrReviewerRequiredMixin(AccessMixin):
    """Allow the view only if the user may change this specific document.

    The rule lives in accounts.backends.ObjectPermissionBackend (owner or Reviewer).
    Not logged in -> redirect to login. Logged in but not allowed -> 403.
    """

    object_permission = "documents.change_document"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        obj = self.get_object()
        if not request.user.has_perm(self.object_permission, obj):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
