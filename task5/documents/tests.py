from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from documents.models import Document

PASSWORD = "Pass12345!"


def make_user(role, name):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password=PASSWORD, role=role)


class RoleMatrixTests(TestCase):
    """Each role tries to view, edit, publish and archive."""

    @classmethod
    def setUpTestData(cls):
        cls.editor = make_user("editor", "ed")              # owns `doc`
        cls.other_editor = make_user("editor", "ed2")       # editor, but not the owner
        cls.reviewer = make_user("reviewer", "rev")
        cls.viewer = make_user("viewer", "view")
        cls.doc = Document.objects.create(title="Plan", content="Body", owner=cls.editor)
        cls.viewer_doc = Document.objects.create(title="Viewer doc", owner=cls.viewer)

    def url(self, name, doc=None):
        return reverse(f"documents:{name}", args=[(doc or self.doc).pk]) if name not in ("list", "create") else reverse(f"documents:{name}")

    # ---------- anonymous ----------
    def test_anonymous_is_sent_to_login(self):
        for name in ("list", "detail", "edit"):
            with self.subTest(name=name):
                response = self.client.get(self.url(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    # ---------- VIEW ----------
    def test_every_role_can_view(self):
        for user in (self.editor, self.reviewer, self.viewer):
            self.client.force_login(user)
            for name in ("list", "detail"):
                with self.subTest(user=user.username, page=name):
                    self.assertEqual(self.client.get(self.url(name)).status_code, 200)

    # ---------- EDIT ----------
    def test_edit_page_access_by_role(self):
        expected = [
            (self.editor, self.doc, 200),          # owner
            (self.other_editor, self.doc, 403),    # editor, not owner
            (self.reviewer, self.doc, 200),        # reviewer edits anything
            (self.viewer, self.doc, 403),          # viewer never edits
            (self.viewer, self.viewer_doc, 403),   # not even their own
        ]
        for user, doc, status in expected:
            with self.subTest(user=user.username, doc=doc.title):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url("edit", doc)).status_code, status)

    def test_owner_and_reviewer_can_save_edit_others_cannot(self):
        self.client.force_login(self.editor)
        self.client.post(self.url("edit"), {"title": "By owner", "content": "x"})
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "By owner")

        self.client.force_login(self.reviewer)
        self.client.post(self.url("edit"), {"title": "By reviewer", "content": "x"})
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "By reviewer")

        for user in (self.other_editor, self.viewer):
            self.client.force_login(user)
            response = self.client.post(self.url("edit"), {"title": "Hacked", "content": "x"})
            self.assertEqual(response.status_code, 403)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "By reviewer")

    # ---------- CREATE ----------
    def test_create_by_role(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url("create")).status_code, 403)

        self.client.force_login(self.editor)
        response = self.client.post(self.url("create"), {"title": "Fresh", "content": "text"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Document.objects.get(title="Fresh").owner, self.editor)

    # ---------- PUBLISH ----------
    def test_only_reviewer_can_publish(self):
        for user in (self.viewer, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.url("publish")).status_code, 403)
                self.doc.refresh_from_db()
                self.assertEqual(self.doc.status, Document.Status.DRAFT)

        self.client.force_login(self.reviewer)
        response = self.client.post(self.url("publish"))
        self.assertEqual(response.status_code, 302)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.PUBLISHED)

    def test_publish_rejects_get(self):
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url("publish")).status_code, 405)

    # ---------- ARCHIVE ----------
    def test_only_reviewer_can_archive(self):
        for user in (self.viewer, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.url("archive")).status_code, 403)
                self.doc.refresh_from_db()
                self.assertNotEqual(self.doc.status, Document.Status.ARCHIVED)

        self.client.force_login(self.reviewer)
        self.client.post(self.url("archive"))
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, Document.Status.ARCHIVED)

    # ---------- BUTTONS HIDDEN IN TEMPLATES ----------
    def test_viewer_sees_no_action_buttons(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url("detail"))
        for name in ("edit", "publish", "archive"):
            self.assertNotContains(response, self.url(name))
        self.assertNotContains(self.client.get(self.url("list")), self.url("create"))

    def test_reviewer_sees_all_action_buttons(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(self.url("detail"))
        for name in ("edit", "publish", "archive"):
            self.assertContains(response, self.url(name))

    def test_editor_sees_edit_only_on_own_document(self):
        other_doc = Document.objects.create(title="Someone else's", owner=self.other_editor)
        self.client.force_login(self.editor)
        response = self.client.get(self.url("list"))
        self.assertContains(response, self.url("edit", self.doc))
        self.assertNotContains(response, self.url("edit", other_doc))
        self.assertNotContains(response, self.url("publish", self.doc))  # editors cannot publish
