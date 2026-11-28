import random
from datetime import timedelta
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from accounts.roles import ROLE_PERMS
from django.contrib.auth.models import Permission
from projects.models import Project, Membership
from tasks.models import Task

class Command(BaseCommand):
    help = "Seed demo users, projects and tasks"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="TeamHub123!")
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first")

    @transaction.atomic
    def handle(self, *args, **o):
        groups = {}
        for name, codes in ROLE_PERMS.items():
            g, _ = Group.objects.get_or_create(name=name)
            perms = Permission.objects.all() if codes == "__all__" else Permission.objects.filter(codename__in=codes)
            g.permissions.set(perms)
            groups[name] = g

        if o["reset"]:
            User.objects.filter(email__endswith="@demo.teamhub").delete()

        def mk(email, name, role, **extra):
            u, created = User.objects.get_or_create(email=email, defaults={"full_name": name, **extra})
            if created:
                u.set_password(o["password"]); u.save()
            u.groups.set([groups[role]])
            return u

        admin = mk("admin@demo.teamhub", "Ada Admin", "Admin", is_staff=True, is_superuser=True)
        managers = [mk("maya@demo.teamhub", "Maya Manager", "Manager", is_staff=True),
                    mk("omar@demo.teamhub", "Omar Manager", "Manager", is_staff=True)]
        members = [mk(f"member{i}@demo.teamhub", n, "Member") for i, n in
                   enumerate(["Sara Khan", "Bilal Ahmed", "Hina Raza", "Usman Ali", "Zoya Malik"], 1)]

        names = ["Website Redesign", "Mobile App", "Q4 Marketing", "Data Pipeline"]
        titles = ["Write spec", "Design mockups", "Review PR", "Fix login bug", "Update docs",
                  "Set up CI", "User interviews", "Deploy staging", "Write tests", "Plan sprint"]
        now = timezone.now()
        for i, pname in enumerate(names):
            project, _ = Project.objects.get_or_create(
                name=pname, defaults={"owner": managers[i % 2], "description": f"Demo project: {pname}"})
            team = random.sample(members, 3)
            for m in team:
                Membership.objects.get_or_create(project=project, user=m)
            if not project.tasks.exists():
                for t in random.sample(titles, 8):
                    Task.objects.create(
                        project=project, title=t, assignee=random.choice(team),
                        status=random.choice(Task.Status.values),
                        due_date=now + timedelta(days=random.randint(-5, 10)),
                        position=random.randint(0, 20))

        call_command("setup_schedules")
        self.stdout.write(self.style.SUCCESS(
            f"Seeded. Login: admin@demo.teamhub / {o['password']} (also maya@, omar@, member1@ ... @demo.teamhub)"))