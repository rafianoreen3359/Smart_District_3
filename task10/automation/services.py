import json

from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask


def sync_digest_task(pref):
    """Create or update the user's own PeriodicTask from their DigestPreference."""
    t = pref.send_time
    lookup = dict(minute=str(t.minute), hour=str(t.hour), day_of_week="1-5",
                  day_of_month="*", month_of_year="*", timezone=settings.TIME_ZONE)
    schedule = CrontabSchedule.objects.filter(**lookup).first() or CrontabSchedule.objects.create(**lookup)

    old_schedule = pref.periodic_task.crontab if pref.periodic_task_id else None
    # update_or_create goes through save(), which tells beat to reload.
    task, _ = PeriodicTask.objects.update_or_create(
        name=f"Daily digest for user {pref.user_id}",
        defaults={
            "task": "automation.tasks.send_daily_digest",
            "crontab": schedule,
            "interval": None,
            "kwargs": json.dumps({"user_id": pref.user_id}),
            "enabled": pref.enabled,
            "description": f"Personal digest for {pref.user} (managed by the settings page).",
        },
    )
    if pref.periodic_task_id != task.pk:
        pref.periodic_task = task
        pref.save(update_fields=["periodic_task"])

    if old_schedule and old_schedule.pk != schedule.pk and not old_schedule.periodictask_set.exists():
        old_schedule.delete()
    return task
