import datetime

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask


class ExchangeRate(models.Model):
    """Latest rate per currency pair, refreshed by sync_exchange_rates."""

    base = models.CharField(max_length=3)
    quote = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    fetched_at = models.DateTimeField()

    class Meta:
        unique_together = [("base", "quote")]
        ordering = ["quote"]

    def __str__(self):
        return f"{self.base}/{self.quote} = {self.rate}"


class DigestPreference(models.Model):
    """One row per user; owns that user's personal PeriodicTask."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="digest_preference"
    )
    send_time = models.TimeField(default=datetime.time(9, 0))
    enabled = models.BooleanField(default=True)
    periodic_task = models.OneToOneField(
        PeriodicTask, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} @ {self.send_time:%H:%M}"


@receiver(post_delete, sender=DigestPreference)
def _drop_periodic_task(sender, instance, **kwargs):
    if instance.periodic_task_id:
        PeriodicTask.objects.filter(pk=instance.periodic_task_id).delete()
