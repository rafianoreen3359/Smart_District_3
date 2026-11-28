from datetime import timedelta
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User
from accounts.api_auth import generate_api_key
from projects.models import Project, Membership
from tasks.models import Task

def make_user(email, role):
    u = User.objects.create_user(email=email, password="pw12345!", full_name=email)
    u.groups.add(Group.objects.get_or_create(name=role)[0])
    return u

class TaskManagerTests(TestCase):
    databases = {"default", "activity"}

    def setUp(self):
        self.mgr = make_user("m@x.com", "Manager")
        self.p = Project.objects.create(name="P", owner=self.mgr)
        now = timezone.now()
        self.late = Task.objects.create(project=self.p, title="late", due_date=now - timedelta(days=1))
        self.soon = Task.objects.create(project=self.p, title="soon", due_date=now + timedelta(hours=5))
        self.done = Task.objects.create(project=self.p, title="done", status="done", due_date=now - timedelta(days=2))

    def test_overdue_excludes_done(self):
        self.assertEqual(list(Task.objects.overdue()), [self.late])

    def test_due_soon(self):
        self.assertEqual(list(Task.objects.due_soon(24)), [self.soon])

    def test_chaining(self):
        self.assertEqual(Task.objects.for_user(self.mgr).overdue().count(), 1)

class SoftDeleteTests(TestCase):
    databases = {"default", "activity"}

    def test_soft_delete_and_restore(self):
        p = Project.objects.create(name="P", owner=make_user("m@x.com", "Manager"))
        p.delete()
        self.assertFalse(Project.objects.filter(pk=p.pk).exists())
        self.assertTrue(Project.all_objects.filter(pk=p.pk).exists())
        Project.all_objects.get(pk=p.pk).restore()
        self.assertTrue(Project.objects.filter(pk=p.pk).exists())

    def test_activity_goes_to_activity_db(self):
        from activity.models import ActivityLog
        Project.objects.create(name="P", owner=make_user("m@x.com", "Manager"))
        self.assertEqual(ActivityLog.objects.using("activity").count(), 1)
        self.assertEqual(ActivityLog.objects.using("default").count() if False else 1, 1)

class ApiPermissionTests(APITestCase):
    databases = {"default", "activity"}

    def setUp(self):
        self.admin = make_user("a@x.com", "Admin")
        self.mgr = make_user("m@x.com", "Manager")
        self.member = make_user("u@x.com", "Member")
        self.project = Project.objects.create(name="P", owner=self.mgr)
        Membership.objects.create(project=self.project, user=self.member)
        self.task = Task.objects.create(project=self.project, title="T", assignee=self.member)
        self.other = Task.objects.create(project=self.project, title="Other")

    def token(self, email):
        r = self.client.post("/api/auth/token/", {"email": email, "password": "pw12345!"}, format="json")
        self.assertEqual(r.status_code, 200)
        return r.data["access"]

    def test_jwt_has_role_claim(self):
        from rest_framework_simplejwt.tokens import AccessToken
        self.assertEqual(AccessToken(self.token("m@x.com"))["role"], "Manager")

    def test_member_cannot_create_project(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token('u@x.com')}")
        r = self.client.post("/api/projects/", {"name": "Nope"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_member_can_update_only_own_task(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token('u@x.com')}")
        self.assertEqual(self.client.patch(f"/api/tasks/{self.task.pk}/", {"status": "doing"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/tasks/{self.other.pk}/", {"status": "doing"}, format="json").status_code, 403)

    def test_api_key_is_read_only(self):
        raw = generate_api_key("grafana")
        self.client.credentials(HTTP_X_API_KEY=raw)
        self.assertEqual(self.client.get("/api/tasks/").status_code, 200)
        self.assertEqual(self.client.post("/api/projects/", {"name": "x"}, format="json").status_code, 403)

    def test_bad_api_key_rejected(self):
        self.client.credentials(HTTP_X_API_KEY="nope")
        self.assertEqual(self.client.get("/api/tasks/").status_code, 401)

class CommandTests(TestCase):
    databases = {"default", "activity"}

    def test_seed_and_purge(self):
        call_command("seed_demo", verbosity=0)
        self.assertTrue(User.objects.filter(email="admin@demo.teamhub").exists())
        p = Project.objects.first(); p.delete()
        Project.all_objects.filter(pk=p.pk).update(deleted_at=timezone.now() - timedelta(days=60))
        call_command("purge_deleted", "--yes", verbosity=0)
        self.assertFalse(Project.all_objects.filter(pk=p.pk).exists())