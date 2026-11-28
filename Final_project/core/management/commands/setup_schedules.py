from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask

SCHEDULES = [
    ("Hourly overdue reminders", "tasks.scheduled.hourly_overdue_reminders", dict(minute="0", hour="*")),
    ("Daily digest",             "tasks.scheduled.daily_digest",             dict(minute="0", hour="8")),
    ("Weekly summary",           "tasks.scheduled.weekly_summary",           dict(minute="0", hour="9", day_of_week="1")),
    ("Nightly cleanup",          "tasks.scheduled.nightly_cleanup",          dict(minute="30", hour="2")),
]

class Command(BaseCommand):
    help = "Create default Celery Beat schedules (editable in admin)"

    def handle(self, *args, **opts):
        for name, task, cron in SCHEDULES:
            schedule, _ = CrontabSchedule.objects.get_or_create(timezone="UTC", **cron)
            PeriodicTask.objects.get_or_create(name=name, defaults={"task": task, "crontab": schedule})
            self.stdout.write(self.style.SUCCESS(f"ready: {name}"))