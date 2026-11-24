from django.core.management.base import BaseCommand

from accounts.models import User
from documents.models import Document

PASSWORD = "Pass12345!"


class Command(BaseCommand):
    help = "Create demo users (one per role) and sample documents."

    def handle(self, *args, **options):
        users = {}
        for username, role, staff in [
            ("admin", User.Role.REVIEWER, True),
            ("editor", User.Role.EDITOR, False),
            ("reviewer", User.Role.REVIEWER, False),
            ("viewer", User.Role.VIEWER, False),
        ]:
            user, created = User.objects.get_or_create(
                email=f"{username}rafia@noreen.com",
                defaults={"username": username, "role": role, "is_staff": staff, "is_superuser": username == "admin"},
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            users[username] = user

        if not Document.objects.exists():
            samples = [
                ("Quarterly report", "Revenue grew 12% quarter over quarter.", Document.Status.DRAFT),
                ("Security policy", "All laptops must use disk encryption.", Document.Status.PUBLISHED),
                ("Onboarding guide", "Welcome! Start with the handbook.", Document.Status.DRAFT),
                ("Old roadmap", "Superseded by the 2026 plan.", Document.Status.ARCHIVED),
            ]
            for title, content, status in samples:
                Document.objects.create(title=title, content=content, status=status, owner=users["editor"])

        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Password for admin / editor / reviewer / viewer rafia@noreen.com: {PASSWORD}"
        ))
