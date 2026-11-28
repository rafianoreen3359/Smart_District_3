import json
from datetime import time
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django_celery_beat.models import PeriodicTask

from .locks import cache_lock
from .models import DigestPreference
from .tasks import sync_exchange_rates

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class LockTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_second_caller_is_refused_then_released(self):
        with cache_lock("k", 60) as first:
            with cache_lock("k", 60) as second:
                self.assertTrue(first)
                self.assertFalse(second)
        with cache_lock("k", 60) as again:
            self.assertTrue(again)

    def test_sync_skips_when_locked(self):
        cache.add("lock:sync_exchange_rates", "someone-else", 60)
        with mock.patch("automation.tasks.requests.get") as get:
            self.assertEqual(sync_exchange_rates(), {"status": "skipped"})
            get.assert_not_called()


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("sam", "sam@example.com", "pw")
        self.client.force_login(self.user)

    def post(self, hhmm, enabled=True):
        data = {"send_time": hhmm}
        if enabled:
            data["enabled"] = "on"
        return self.client.post(reverse("automation:settings"), data)

    def test_creates_then_updates_own_periodic_task(self):
        self.post("07:30")
        name = f"Daily digest for user {self.user.pk}"
        task = PeriodicTask.objects.get(name=name)
        self.assertEqual((task.crontab.hour, task.crontab.minute, task.crontab.day_of_week),
                         ("7", "30", "1-5"))
        self.assertEqual(json.loads(task.kwargs), {"user_id": self.user.pk})

        self.post("18:05", enabled=False)
        self.assertEqual(PeriodicTask.objects.filter(name=name).count(), 1)
        task.refresh_from_db()
        self.assertEqual((task.crontab.hour, task.crontab.minute), ("18", "5"))
        self.assertFalse(task.enabled)
        self.assertEqual(DigestPreference.objects.get().send_time, time(18, 5))
