from django.db import models

class ActivityLog(models.Model):
    # Plain integers, not ForeignKeys: a FK can't span two databases.
    actor_id = models.PositiveIntegerField(null=True, db_index=True)
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=40)           # created / updated / deleted / restored
    target_type = models.CharField(max_length=40)      # project / task
    target_id = models.PositiveIntegerField()
    project_id = models.PositiveIntegerField(null=True, db_index=True)
    summary = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]