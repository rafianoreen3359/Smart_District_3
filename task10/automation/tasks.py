import logging
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from smtplib import SMTPException

import requests
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, Q
from django.template.loader import render_to_string
from django.utils import timezone

from .locks import cache_lock
from .models import ExchangeRate

logger = logging.getLogger(__name__)


def _report_model():
    # Day 9's model; configurable so the app doesn't hard-depend on its name.
    return apps.get_model(getattr(settings, "LEDGERLINE_REPORT_MODEL", "reports.ReportRequest"))


# ---------------------------------------------------------------- cleanup ---
@shared_task(name="automation.tasks.cleanup_expired_reports")
def cleanup_expired_reports():
    days = getattr(settings, "REPORT_RETENTION_DAYS", 7)
    field = getattr(settings, "REPORT_FILE_FIELD", "file")
    cutoff = timezone.now() - timedelta(days=days)
    Report = _report_model()

    removed = 0
    stale = (
        Report.objects.filter(created_at__lt=cutoff)
        .exclude(**{f"{field}__isnull": True})
        .exclude(**{field: ""})
    )
    for report in stale.iterator():
        getattr(report, field).delete(save=False)  # removes the file from storage
        report.save(update_fields=[field])
        removed += 1

    # Sweep orphaned files on disk that no row points at any more.
    orphans = 0
    directory = Path(getattr(settings, "REPORT_DIR", Path(settings.MEDIA_ROOT) / "reports"))
    if directory.is_dir():
        limit = cutoff.timestamp()
        for path in directory.iterdir():
            if path.is_file() and path.stat().st_mtime < limit:
                path.unlink(missing_ok=True)
                orphans += 1

    logger.info("cleanup_expired_reports: %s files via DB, %s orphans", removed, orphans)
    return {"removed": removed, "orphans": orphans}


# ------------------------------------------------------------ email helpers ---
def _day_bounds(days_back: int, span_days: int = 1):
    tz = timezone.get_current_timezone()
    start_date = timezone.localdate() - timedelta(days=days_back)
    start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    return start, start + timedelta(days=span_days)


def _summary(user, start, end):
    qs = _report_model().objects.filter(user=user, created_at__gte=start, created_at__lt=end)
    return qs.aggregate(
        total=Count("id"),
        done=Count("id", filter=Q(status__iexact="done")),
        failed=Count("id", filter=Q(status__iexact="failed")),
        pending=Count("id", filter=~Q(status__iexact="done") & ~Q(status__iexact="failed")),
    )


def _send_summary(user, subject, heading, period_label, stats):
    ctx = {"user": user, "heading": heading, "period": period_label, "stats": stats}
    text = (
        f"{heading} ({period_label})\n\n"
        f"Reports requested: {stats['total']}\nCompleted: {stats['done']}\n"
        f"Failed: {stats['failed']}\nIn progress: {stats['pending']}\n"
    )
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(render_to_string("automation/email/summary.html", ctx), "text/html")
    msg.send()


# ------------------------------------------------------------ daily digest ---
@shared_task(
    name="automation.tasks.send_daily_digest",
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_daily_digest(user_id=None):
    """user_id given  -> that user's personal schedule: send directly.
    user_id omitted -> shared 09:00 schedule: fan out to users with no personal
    preference (users who chose their own time or opted out are skipped)."""
    User = get_user_model()
    if user_id is None:
        ids = list(
            User.objects.filter(is_active=True, digest_preference__isnull=True)
            .exclude(email="")
            .values_list("pk", flat=True)
        )
        for pk in ids:
            send_daily_digest.delay(user_id=pk)
        return {"queued": len(ids)}

    user = User.objects.filter(pk=user_id, is_active=True).exclude(email="").first()
    if not user:
        return {"sent": 0}
    start, end = _day_bounds(1)
    _send_summary(user, "Your Ledgerline daily digest", "Yesterday on Ledgerline",
                  f"{start:%A %d %B}", _summary(user, start, end))
    return {"sent": 1}


# ------------------------------------------------------------ weekly report ---
@shared_task(name="automation.tasks.send_weekly_report")
def send_weekly_report():
    start, _ = _day_bounds(7)
    _, end = _day_bounds(1)
    User = get_user_model()
    sent = failed = 0
    for user in User.objects.filter(is_active=True).exclude(email="").iterator():
        try:
            _send_summary(user, "Your Ledgerline weekly report", "Your week on Ledgerline",
                          f"{start:%d %b} – {(end - timedelta(seconds=1)):%d %b}",
                          _summary(user, start, end))
            sent += 1
        except Exception:
            logger.exception("weekly report failed for user %s", user.pk)
            failed += 1
    return {"sent": sent, "failed": failed}


# ----------------------------------------------------------- exchange rates ---
@shared_task(name="automation.tasks.sync_exchange_rates", soft_time_limit=120, time_limit=150)
def sync_exchange_rates():
    base = getattr(settings, "EXCHANGE_BASE", "USD")
    symbols = getattr(settings, "EXCHANGE_SYMBOLS", ["EUR", "GBP", "PKR", "JPY", "AED", "CAD"])
    url = getattr(settings, "EXCHANGE_API_URL", "https://open.er-api.com/v6/latest/{base}").format(base=base)

    # Lock expiry (10 min) is longer than the hard time limit (150 s).
    with cache_lock("lock:sync_exchange_rates", timeout=600) as acquired:
        if not acquired:
            logger.info("sync_exchange_rates skipped: already running")
            return {"status": "skipped"}
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            raise RuntimeError(f"Rates API error: {data}")
        now = timezone.now()
        saved = 0
        for sym in symbols:
            if sym in data["rates"]:
                ExchangeRate.objects.update_or_create(
                    base=base, quote=sym,
                    defaults={"rate": Decimal(str(data["rates"][sym])), "fetched_at": now},
                )
                saved += 1
        return {"status": "ok", "saved": saved}
