from .models import ActivityLog

def log(actor, action, obj, summary="", project_id=None):
    ActivityLog.objects.create(
        actor_id=getattr(actor, "pk", None),
        actor_email=getattr(actor, "email", ""),
        action=action,
        target_type=obj._meta.model_name,
        target_id=obj.pk,
        project_id=project_id,
        summary=summary[:300],
    )