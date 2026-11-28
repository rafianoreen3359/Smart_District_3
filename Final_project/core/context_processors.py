from django.conf import settings

def workspace(request):
    ctx = {"WORKSPACE_NAME": getattr(settings, "WORKSPACE_NAME", "TeamHub")}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["unread_notifications"] = user.notifications.filter(is_read=False).count()
        pid = request.session.get("active_project_id")
        if pid:
            from projects.models import Project
            ctx["active_project"] = Project.objects.filter(pk=pid).first()
    return ctx