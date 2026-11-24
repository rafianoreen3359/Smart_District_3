import hashlib

from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from api import permissions as perms
from api.models import APIKey
from api.serializers import RoleTokenObtainPairSerializer
from documents.models import Document

PASSWORD = "Pass12345!"


def make_user(role, name):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password=PASSWORD, role=role)


class APIBase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(email="admin@example.com", username="admin", password=PASSWORD)
        cls.reviewer = make_user("reviewer", "rev")
        cls.editor = make_user("editor", "ed")
        cls.other = make_user("editor", "ed2")
        cls.viewer = make_user("viewer", "view")

        published = Document.Status.PUBLISHED
        cls.ed_draft = Document.objects.create(title="Ed draft", owner=cls.editor)
        cls.ed_pub = Document.objects.create(title="Ed pub", owner=cls.editor, status=published)
        cls.other_draft = Document.objects.create(title="Other draft", owner=cls.other)
        cls.other_pub = Document.objects.create(title="Other pub", owner=cls.other, status=published)
        cls.all_docs = {cls.ed_draft, cls.ed_pub, cls.other_draft, cls.other_pub}

        cls.api_key, cls.raw_key = APIKey.create_with_key("reader", cls.viewer)

    # ---- helpers ----
    def as_user(self, user):
        token = RoleTokenObtainPairSerializer.get_token(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def as_key(self, raw):
        self.client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw}")

    def as_anon(self):
        self.client.credentials()

    @staticmethod
    def detail_url(doc):
        return reverse("api:document-detail", args=[doc.pk])

    @staticmethod
    def action_url(doc, name):
        return reverse(f"api:document-{name}", args=[doc.pk])

    @staticmethod
    def message(response):
        return str(response.data["detail"])


# =============================== AUTHENTICATION ===============================
class AuthenticationTests(APIBase):
    def test_no_credentials_gives_401(self):
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_token_endpoint_returns_tokens_with_role_and_email_claims(self):
        response = self.client.post(reverse("api:token_obtain_pair"), {"email": "ed@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        claims = AccessToken(response.data["access"])
        self.assertEqual(claims["role"], "editor")
        self.assertEqual(claims["email"], "ed@example.com")
        self.assertIn("refresh", response.data)

    def test_token_endpoint_also_accepts_username(self):
        response = self.client.post(reverse("api:token_obtain_pair"), {"email": "ed", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_gives_401(self):
        response = self.client.post(reverse("api:token_obtain_pair"), {"email": "ed@example.com", "password": "nope"})
        self.assertEqual(response.status_code, 401)

    def test_account_locks_after_five_failed_token_requests(self):
        for _ in range(5):
            self.client.post(reverse("api:token_obtain_pair"), {"email": "ed@example.com", "password": "nope"})
        response = self.client.post(reverse("api:token_obtain_pair"), {"email": "ed@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 401)

    def test_refresh_endpoint_works(self):
        tokens = self.client.post(
            reverse("api:token_obtain_pair"), {"email": "ed@example.com", "password": PASSWORD}
        ).data
        response = self.client.post(reverse("api:token_refresh"), {"refresh": tokens["refresh"]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

    def test_garbage_bearer_token_gives_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_existing_token_stops_working_when_account_is_locked(self):
        self.as_user(self.editor)
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 200)
        User.objects.filter(pk=self.editor.pk).update(is_locked=True)
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_valid_api_key_authenticates(self):
        self.as_key(self.raw_key)
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 200)

    def test_invalid_api_key_gives_401(self):
        self.as_key("definitely-not-a-real-key")
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_revoked_api_key_gives_401(self):
        self.api_key.revoke()
        self.as_key(self.raw_key)
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_api_key_of_locked_owner_gives_401(self):
        User.objects.filter(pk=self.viewer.pk).update(is_locked=True)
        self.as_key(self.raw_key)
        self.assertEqual(self.client.get(reverse("api:document-list")).status_code, 401)

    def test_api_key_is_stored_hashed_only(self):
        stored = APIKey.objects.get(pk=self.api_key.pk)
        self.assertEqual(len(stored.key_hash), 64)
        self.assertEqual(stored.key_hash, hashlib.sha256(self.raw_key.encode()).hexdigest())
        self.assertNotEqual(stored.key_hash, self.raw_key)
        for value in (stored.name, stored.prefix, stored.key_hash, stored.scopes):
            self.assertNotEqual(value, self.raw_key)
        self.assertEqual(stored.prefix, self.raw_key[:8])

    def test_using_a_key_records_last_used(self):
        self.assertIsNone(APIKey.objects.get(pk=self.api_key.pk).last_used_at)
        self.as_key(self.raw_key)
        self.client.get(reverse("api:document-list"))
        self.assertIsNotNone(APIKey.objects.get(pk=self.api_key.pk).last_used_at)


# =============================== LIST / RETRIEVE ===============================
class ListRetrieveTests(APIBase):
    def ids(self, response):
        return {item["id"] for item in response.data["results"]}

    def test_list_returns_only_documents_each_role_may_see(self):
        cases = [
            (self.viewer, {self.ed_pub, self.other_pub}),                              # published only
            (self.editor, {self.ed_draft, self.ed_pub, self.other_pub}),               # own + published
            (self.other, {self.other_draft, self.other_pub, self.ed_pub}),
            (self.reviewer, self.all_docs),
            (self.admin, self.all_docs),
        ]
        for user, expected in cases:
            with self.subTest(user=user.username):
                self.as_user(user)
                response = self.client.get(reverse("api:document-list"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.ids(response), {d.pk for d in expected})

    def test_list_with_api_key_shows_published_only(self):
        self.as_key(self.raw_key)
        response = self.client.get(reverse("api:document-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), {self.ed_pub.pk, self.other_pub.pk})

    def test_api_key_without_read_scope_is_forbidden(self):
        _, raw = APIKey.create_with_key("no-scope", self.viewer, scopes="")
        self.as_key(raw)
        response = self.client.get(reverse("api:document-list"))
        self.assertEqual(response.status_code, 403)
        self.assertIn("documents:read", self.message(response))

    def test_retrieve_respects_visibility(self):
        cases = [
            (self.viewer, self.ed_draft, 404),
            (self.viewer, self.ed_pub, 200),
            (self.editor, self.other_draft, 404),
            (self.editor, self.ed_draft, 200),
            (self.reviewer, self.ed_draft, 200),
            (self.admin, self.other_draft, 200),
        ]
        for user, doc, expected in cases:
            with self.subTest(user=user.username, doc=doc.title):
                self.as_user(user)
                self.assertEqual(self.client.get(self.detail_url(doc)).status_code, expected)

    def test_retrieve_with_api_key(self):
        self.as_key(self.raw_key)
        self.assertEqual(self.client.get(self.detail_url(self.ed_pub)).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url(self.ed_draft)).status_code, 404)

    def test_anonymous_cannot_list_or_retrieve(self):
        self.assertEqual(self.client.get(self.detail_url(self.ed_pub)).status_code, 401)


# =============================== CREATE ===============================
class CreateTests(APIBase):
    payload = {"title": "Brand new", "content": "Hello"}

    def post(self):
        return self.client.post(reverse("api:document-list"), self.payload, format="json")

    def test_editor_can_create_and_becomes_owner(self):
        self.as_user(self.editor)
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["owner"], self.editor.pk)
        self.assertEqual(response.data["status"], "draft")

    def test_admin_can_create(self):
        self.as_user(self.admin)
        self.assertEqual(self.post().status_code, 201)

    def test_viewer_and_reviewer_cannot_create(self):
        for user in (self.viewer, self.reviewer):
            with self.subTest(user=user.username):
                self.as_user(user)
                response = self.post()
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.message(response), perms.CanCreateDocument.message)

    def test_api_key_cannot_create(self):
        self.as_key(self.raw_key)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertIn("read-only", self.message(response))

    def test_anonymous_cannot_create(self):
        self.assertEqual(self.post().status_code, 401)


# =============================== UPDATE ===============================
class UpdateTests(APIBase):
    def patch(self, doc, title="Changed"):
        return self.client.patch(self.detail_url(doc), {"title": title}, format="json")

    def test_edit_by_actor(self):
        cases = [
            (self.editor, self.ed_pub, 200),       # owner
            (self.editor, self.ed_draft, 200),     # owner of a draft
            (self.other, self.ed_pub, 403),        # editor who is not the owner
            (self.other, self.ed_draft, 404),      # cannot even see it
            (self.reviewer, self.ed_draft, 200),   # reviewer edits anything
            (self.admin, self.other_pub, 200),
            (self.viewer, self.ed_pub, 403),
        ]
        for user, doc, expected in cases:
            with self.subTest(user=user.username, doc=doc.title):
                self.as_user(user)
                self.assertEqual(self.patch(doc).status_code, expected)

    def test_forbidden_edit_uses_custom_message_and_changes_nothing(self):
        for user in (self.other, self.viewer):
            with self.subTest(user=user.username):
                self.as_user(user)
                response = self.patch(self.ed_pub, "Hacked")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.message(response), perms.OwnerOrReviewer.message)
        self.ed_pub.refresh_from_db()
        self.assertEqual(self.ed_pub.title, "Ed pub")

    def test_put_by_owner_and_reviewer(self):
        for user in (self.editor, self.reviewer):
            with self.subTest(user=user.username):
                self.as_user(user)
                response = self.client.put(
                    self.detail_url(self.ed_pub), {"title": f"By {user.username}", "content": "x"}, format="json"
                )
                self.assertEqual(response.status_code, 200)

    def test_api_key_cannot_edit(self):
        self.as_key(self.raw_key)
        response = self.patch(self.ed_pub)
        self.assertEqual(response.status_code, 403)
        self.assertIn("read-only", self.message(response))

    def test_anonymous_cannot_edit(self):
        self.assertEqual(self.patch(self.ed_pub).status_code, 401)

    def test_status_cannot_be_changed_through_edit(self):
        self.as_user(self.editor)
        response = self.client.patch(self.detail_url(self.ed_draft), {"status": "published"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.ed_draft.refresh_from_db()
        self.assertEqual(self.ed_draft.status, Document.Status.DRAFT)


# =============================== DELETE ===============================
class DeleteTests(APIBase):
    def test_only_admin_can_delete(self):
        self.as_user(self.admin)
        response = self.client.delete(self.detail_url(self.ed_pub))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Document.objects.filter(pk=self.ed_pub.pk).exists())

    def test_everyone_else_gets_403_with_custom_message(self):
        for user in (self.reviewer, self.editor, self.viewer):
            with self.subTest(user=user.username):
                self.as_user(user)
                response = self.client.delete(self.detail_url(self.ed_pub))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.message(response), perms.IsAdmin.message)
        self.assertTrue(Document.objects.filter(pk=self.ed_pub.pk).exists())

    def test_api_key_cannot_delete(self):
        self.as_key(self.raw_key)
        response = self.client.delete(self.detail_url(self.ed_pub))
        self.assertEqual(response.status_code, 403)
        self.assertIn("read-only", self.message(response))
        self.assertTrue(Document.objects.filter(pk=self.ed_pub.pk).exists())

    def test_anonymous_cannot_delete(self):
        self.assertEqual(self.client.delete(self.detail_url(self.ed_pub)).status_code, 401)


# =============================== PUBLISH / ARCHIVE ===============================
class PublishArchiveTests(APIBase):
    def test_reviewer_and_admin_can_publish(self):
        for user in (self.reviewer, self.admin):
            with self.subTest(user=user.username):
                Document.objects.filter(pk=self.ed_draft.pk).update(status=Document.Status.DRAFT)
                self.as_user(user)
                response = self.client.post(self.action_url(self.ed_draft, "publish"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["status"], "published")

    def test_publish_twice_is_a_400(self):
        self.as_user(self.reviewer)
        self.client.post(self.action_url(self.ed_draft, "publish"))
        response = self.client.post(self.action_url(self.ed_draft, "publish"))
        self.assertEqual(response.status_code, 400)

    def test_reviewer_can_archive(self):
        self.as_user(self.reviewer)
        response = self.client.post(self.action_url(self.ed_pub, "archive"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "archived")

    def test_editor_and_viewer_cannot_publish_or_archive(self):
        for user in (self.editor, self.viewer):
            for name, doc in (("publish", self.ed_draft), ("archive", self.ed_pub)):
                with self.subTest(user=user.username, action=name):
                    self.as_user(user)
                    response = self.client.post(self.action_url(doc, name))
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(self.message(response), perms.IsReviewer.message)

    def test_api_key_cannot_publish_or_archive(self):
        self.as_key(self.raw_key)
        for name in ("publish", "archive"):
            with self.subTest(action=name):
                response = self.client.post(self.action_url(self.ed_pub, name))
                self.assertEqual(response.status_code, 403)
                self.assertIn("read-only", self.message(response))

    def test_anonymous_cannot_publish(self):
        self.assertEqual(self.client.post(self.action_url(self.ed_draft, "publish")).status_code, 401)


# =============================== PERMISSION CLASSES ===============================
class PermissionMessageTests(APIBase):
    def test_every_permission_class_has_its_own_403_message(self):
        classes = [
            perms.IsAuthenticatedUser,
            perms.IsOwner,
            perms.IsReviewer,
            perms.IsAdmin,
            perms.CanCreateDocument,
            perms.HasValidAPIKeyScope,
            perms.OwnerOrReviewer,
        ]
        messages = [cls.message for cls in classes]
        self.assertTrue(all(messages))
        self.assertEqual(len(set(messages)), len(messages))  # all different

    def test_console_page_loads(self):
        response = self.client.get(reverse("api:console"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API Console")
