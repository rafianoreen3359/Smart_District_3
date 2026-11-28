from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from projects.models import Project

class Command(BaseCommand):
    help = "Permanently delete soft-deleted projects older than N days"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true", help="Skip confirmation")

    def handle(self, *a, **o):
        cutoff = timezone.now() - timedelta(days=o["days"])
        qs = Project.all_objects.filter(deleted_at__lt=cutoff)
        n = qs.count()
        self.stdout.write(f"{n} project(s) deleted before {cutoff:%Y-%m-%d}")
        if o["dry_run"] or n == 0:
            return
        if not o["yes"] and input("Permanently delete? [y/N] ").lower() != "y":
            self.stdout.write("Aborted"); return
        for p in qs:
            p.hard_delete()
        self.stdout.write(self.style.SUCCESS(f"Purged {n}"))