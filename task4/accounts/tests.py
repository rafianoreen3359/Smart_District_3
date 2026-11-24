from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.backends import MAX_FAILED_ATTEMPTS, ObjectPermissionBackend
from accounts.models import User
from documents.models import Document

PASSWORD = "Pass12345!"


def make_user(role, name):
    return User.objects.create_user(email=f"{name}@noreen.com", username=name, password=PASSWORD, role=role)


class GroupMigrationTests(TestCase):
    """The data migration must have created the three groups with the right permissions."""

    def codenames(self, group_name):
        return set(Group.objects.get(name=group_name).permissions.values_list("codename", flat=True))

    def test_three_groups_exist(self):
        names = set(Group.objects.values_list("name", flat=True))
        self.assertTrue({"Editor", "Reviewer", "Viewer"}.issubset(names))

    def test_group_permissions(self):
        self.assertEqual(self.codenames("Viewer"), {"view_document"})
        self.assertEqual(self.codenames("Editor"), {"view_document", "add_document", "change_document"})
        self.assertEqual(
            self.codenames("Reviewer"),
            {"view_document", "change_document", "publish_document", "archive_document"},
        )

    def test_role_puts_user_in_matching_group(self):
        user = make_user("editor", "ed")
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Editor"])
        user.role = User.Role.REVIEWER
        user.save()
        self.assertEqual(list(user.groups.values_list("name", flat=True)), ["Reviewer"])


class LoginBackendTests(TestCase):
    def setUp(self):
        self.user = make_user("viewer", "vera")

    def test_login_with_email(self):
        self.assertTrue(self.client.login(username="rafia@noreen.com", password=PASSWORD))

    def test_login_with_username(self):
        self.assertTrue(self.client.login(username="Rafia", password=PASSWORD))

    def test_wrong_password_rejected(self):
        self.assertFalse(self.client.login(username="Rafia", password="nope"))

    def test_locks_after_five_failed_attempts(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.assertIsNone(authenticate(username="rafia@noreen.com", password="wrong"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_locked)
        self.assertEqual(self.user.failed_login_attempts, MAX_FAILED_ATTEMPTS)
        # the right password no longer works
        self.assertIsNone(authenticate(username="rafia@noreen.com", password=PASSWORD))

    def test_four_failures_do_not_lock_and_success_resets_counter(self):
        for _ in range(MAX_FAILED_ATTEMPTS - 1):
            authenticate(username="Rafia", password="wrong")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_locked)
        self.assertIsNotNone(authenticate(username="Rafia", password=PASSWORD))
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)

    def test_unlock_lets_user_back_in(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            authenticate(username="Rafia", password="wrong")
        User.objects.filter(pk=self.user.pk).update(is_locked=False, failed_login_attempts=0)
        self.assertIsNotNone(authenticate(username="Rafia", password=PASSWORD))

    def test_login_page_shows_locked_message(self):
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.post(reverse("login"), {"username": "Rafia", "password": "wrong"})
        response = self.client.post(reverse("login"), {"username": "Rafia", "password": PASSWORD})
        self.assertContains(response, "locked")

    def test_signup_creates_viewer(self):
        response = self.client.post(
            reverse("signup"),
            {"email": "rafia@noreen.com", "username": "Noreen", "password1": "Str0ng-Pass-77", "password2": "Str0ng-Pass-77"},
        )
        self.assertEqual(response.status_code, 302)
        new = User.objects.get(email="rafia@noreen.com")
        self.assertEqual(new.role, User.Role.VIEWER)
        self.assertEqual(list(new.groups.values_list("name", flat=True)), ["Viewer"])


class ObjectPermissionBackendTests(TestCase):
    def setUp(self):
        self.editor = make_user("editor", "ed")
        self.other_editor = make_user("editor", "ed2")
        self.reviewer = make_user("reviewer", "rev")
        self.viewer = make_user("viewer", "view")
        self.doc = Document.objects.create(title="Doc", owner=self.editor)
        self.viewer_doc = Document.objects.create(title="Mine", owner=self.viewer)

    def test_owner_can_change(self):
        self.assertTrue(self.editor.has_perm("documents.change_document", self.doc))

    def test_reviewer_can_change_anyones(self):
        self.assertTrue(self.reviewer.has_perm("documents.change_document", self.doc))

    def test_other_editor_cannot_change(self):
        self.assertFalse(self.other_editor.has_perm("documents.change_document", self.doc))

    def test_viewer_cannot_change_even_own_document(self):
        self.assertFalse(self.viewer.has_perm("documents.change_document", self.viewer_doc))

    def test_backend_ignores_calls_without_object(self):
        self.assertFalse(ObjectPermissionBackend().has_perm(self.reviewer, "documents.change_document"))

    def test_model_level_publish_and_archive_permissions(self):
        self.assertTrue(self.reviewer.has_perm("documents.publish_document"))
        self.assertTrue(self.reviewer.has_perm("documents.archive_document"))
        self.assertFalse(self.editor.has_perm("documents.publish_document"))
        self.assertFalse(self.viewer.has_perm("documents.archive_document"))
