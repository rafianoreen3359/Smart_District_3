from django.core.management.base import BaseCommand

from chat.models import Presence


class Command(BaseCommand):
    help = "Delete presence rows left behind if the server was killed. Run at deploy time."

    def handle(self, *args, **options):
        count, _ = Presence.objects.all().delete()
        self.stdout.write(f"Removed {count} stale presence row(s).")
