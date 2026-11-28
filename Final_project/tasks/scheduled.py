from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Task
from notifications.services import notify  # type: ignore[import-not-found]

User = get_user_model()

@shared_task
def hourly_overdue_reminders():
    count = 0
    for user in User.objects.filter(is_active=True, assigned_tasks__in=Task.objects.overdue()).distinct():
        late = Task.objects.overdue().filter(assignee=user)
        # only nudge once per 24h per user
        from django.core.cache import cache
        key = f"overdue-nudge:{user.pk}"
        if cache.add(key, 1, timeout=24 * 3600):
            notify(user, f"{late.count()} overdue task(s)", ", ".join(t.title for t in late[:3]), "/")
            count += 1
    return f"nudged {count} users"

@shared_task
def daily_digest():
    sent = 0
    for user in User.objects.filter(is_active=True):
        mine = Task.objects.filter(assignee=user)
        due_soon, overdue = mine.due_soon(24), mine.overdue()
        if not (due_soon.exists() or overdue.exists()):
            continue
        body = (f"Good morning {user.full_name or user.email},\n\n"
                f"Overdue ({overdue.count()}):\n" + "\n".join(f"  - {t.title}" for t in overdue) +
                f"\n\nDue in 24h ({due_soon.count()}):\n" + "\n".join(f"  - {t.title}" for t in due_soon))
        send_mail("Your TeamHub daily digest", body, settings.DEFAULT_FROM_EMAIL, [user.email])
        sent += 1
    return f"{sent} digests"

@shared_task
def weekly_summary():
    since = timezone.now() - timedelta(days=7)
    sent = 0
    for user in User.objects.filter(groups__name__in=["Admin", "Manager"], is_active=True).distinct():
        qs = Task.objects.for_user(user)
        done = qs.filter(status=Task.Status.DONE, created_at__gte=since).count()
        body = (f"Weekly summary\n\nCreated this week: {qs.filter(created_at__gte=since).count()}\n"
                f"Completed: {done}\nCurrently overdue: {qs.overdue().count()}\n")
        send_mail("TeamHub weekly summary", body, settings.DEFAULT_FROM_EMAIL, [user.email])
        sent += 1
    return f"{sent} summaries"

@shared_task
def nightly_cleanup():
    from projects.models import Project
    from notifications.models import Notification  # type: ignore[import-not-found]
    cutoff = timezone.now() - timedelta(days=30)
    purged = Project.all_objects.filter(deleted_at__lt=cutoff)
    n_projects = purged.count()
    for p in purged:
        p.hard_delete()
    n_notifs, _ = Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
    return f"purged {n_projects} projects, {n_notifs} notifications"