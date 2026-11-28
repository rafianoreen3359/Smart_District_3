from django.db.models.signals import post_save
from django.dispatch import receiver
from importlib import import_module

try:
    get_current_user = import_module("core" + ".current_user").get_current_user
except ModuleNotFoundError:
    def get_current_user():
        return None

from projects.models import Project
from tasks.models import Task
from .services import log

def _actor():
    u = get_current_user()
    return u if u is not None and getattr(u, "is_authenticated", False) and getattr(u, "pk", None) else None

@receiver(post_save, sender=Project)
def project_saved(sender, instance, created, **kw):
    if instance.deleted_at:
        action = "deleted"
    else:
        action = "created" if created else "updated"
    log(_actor(), action, instance, f"Project “{instance.name}” {action}", project_id=instance.pk)

@receiver(post_save, sender=Task)
def task_saved(sender, instance, created, **kw):
    action = "created" if created else "updated"
    log(_actor(), action, instance, f"Task “{instance.title}” {action} ({instance.status})",
        project_id=instance.project_id)