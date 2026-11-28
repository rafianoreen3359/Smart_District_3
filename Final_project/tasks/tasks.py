import csv
import logging
import smtplib
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

log = logging.getLogger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(smtplib.SMTPException, ConnectionError, TimeoutError),
    retry_backoff=True,          # 1s, 2s, 4s, ...
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_assignment_email(self, task_id):
    from .models import Task
    try:
        task = Task.objects.select_related("assignee", "project").get(pk=task_id)
    except Task.DoesNotExist:
        return "task gone"
    if not task.assignee:
        return "no assignee"
    ctx = {"task": task, "url": f"{settings.SITE_URL}/projects/{task.project_id}/board/"}
    send_mail(
        subject=f"[{task.project.name}] You were assigned: {task.title}",
        message=render_to_string("emails/assignment.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[task.assignee.email],
        html_message=render_to_string("emails/assignment.html", ctx),
    )
    return f"sent to {task.assignee.email}"


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def generate_project_report(self, project_id, requested_by_id=None):
    from projects.models import Project
    from .models import Task
    settings.REPORTS_DIR.mkdir(exist_ok=True)
    project = Project.all_objects.get(pk=project_id)
    path = settings.REPORTS_DIR / f"project_{project.pk}_{project.name[:30].replace(' ', '_')}.csv"
    tasks = Task.objects.filter(project=project).select_related("assignee")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Title", "Status", "Assignee", "Due", "Overdue"])
        overdue_ids = set(tasks.overdue().values_list("id", flat=True))
        for t in tasks:
            w.writerow([t.id, t.title, t.status, t.assignee.email if t.assignee else "",
                        t.due_date.isoformat() if t.due_date else "", t.id in overdue_ids])
    if requested_by_id:
        from accounts.models import User
        from django.utils.module_loading import import_string

        try:
            notify = import_string("notifications.services.notify")
        except ImportError:
            notify = import_string("apps.notifications.services.notify")
        notify(User.objects.get(pk=requested_by_id), f"Report ready: {project.name}", str(path.name))
    return str(path)