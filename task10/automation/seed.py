"""Default schedules. Works with real models (management command) and
historical models (data migration) because the model classes are passed in."""
from django.conf import settings

SCHEDULES = [
    {
        "name": "Cleanup expired reports (nightly 02:00)",
        "task": "automation.tasks.cleanup_expired_reports",
        "cron": {"minute": "0", "hour": "2", "day_of_week": "*"},
        "description": "Deletes report files older than the retention period (7 days).",
    },
    {
        "name": "Send daily digest (Mon-Fri 09:00)",
        "task": "automation.tasks.send_daily_digest",
        "cron": {"minute": "0", "hour": "9", "day_of_week": "1-5"},
        "description": "Default digest for users who have not picked their own time.",
    },
    {
        "name": "Sync exchange rates (every 30 min)",
        "task": "automation.tasks.sync_exchange_rates",
        "interval": {"every": 30, "period": "minutes"},
        "description": "Fetches rates from the public API; guarded by a cache lock.",
    },
    {
        "name": "Send weekly report (Sundays 08:00)",
        "task": "automation.tasks.send_weekly_report",
        "cron": {"minute": "0", "hour": "8", "day_of_week": "0"},
        "description": "Emails each user a summary of the last 7 days.",
    },
]


def _first_or_create(model, **lookup):
    obj = model.objects.filter(**lookup).first()
    return obj or model.objects.create(**lookup)


def seed(CrontabSchedule, IntervalSchedule, PeriodicTask, reset=False):
    tz = settings.TIME_ZONE
    for spec in SCHEDULES:
        defaults = {"task": spec["task"], "description": spec["description"], "enabled": True}
        if "cron" in spec:
            defaults["crontab"] = _first_or_create(
                CrontabSchedule, day_of_month="*", month_of_year="*", timezone=tz, **spec["cron"]
            )
        else:
            defaults["interval"] = _first_or_create(IntervalSchedule, **spec["interval"])
        if reset:
            PeriodicTask.objects.update_or_create(name=spec["name"], defaults=defaults)
        else:
            # get_or_create: never overwrite what an admin has edited.
            PeriodicTask.objects.get_or_create(name=spec["name"], defaults=defaults)


def unseed(PeriodicTask):
    PeriodicTask.objects.filter(name__in=[s["name"] for s in SCHEDULES]).delete()
