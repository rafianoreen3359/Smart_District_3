from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from automation.seed import SCHEDULES, seed


class Command(BaseCommand):
    help = "Create the four default periodic tasks (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Overwrite existing tasks with the defaults.")

    def handle(self, *args, **opts):
        seed(CrontabSchedule, IntervalSchedule, PeriodicTask, reset=opts["reset"])
        self.stdout.write(self.style.SUCCESS(f"{len(SCHEDULES)} schedules ensured."))
