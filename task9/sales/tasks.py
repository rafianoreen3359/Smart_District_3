"""
Celery tasks.

Report pipeline (chain):   generate_report  ->  send_report_email
Image pipeline (chord):    group(resize_image x3)  ->  mark_product_processed
"""
import csv
import io
import logging
import smtplib
import time
from datetime import timedelta
from decimal import Decimal

from celery import chain, chord, group, shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps

from .models import Product, ProductImage, ReportRequest

log = logging.getLogger(__name__)

IMAGE_SIZES = {"thumb": 150, "medium": 480, "large": 1024}


# --------------------------------------------------------------------------- #
# Enqueue helpers - called from transaction.on_commit() in the views
# --------------------------------------------------------------------------- #
def enqueue_report(report_id):
    """generate_report -> send_report_email. The chain feeds the first task's return value
    (the report id) into the second task."""
    report_id = str(report_id)
    result = chain(generate_report.s(report_id), send_report_email.s()).apply_async()
    first = result.parent or result
    ReportRequest.objects.filter(pk=report_id).update(task_id=first.id, email_task_id=result.id)
    return result


def enqueue_product(product_id):
    """group of 3 resizes in parallel, then a chord callback marks the product processed."""
    header = group(resize_image.s(product_id, label, px) for label, px in IMAGE_SIZES.items())
    callback = mark_product_processed.s(product_id)
    callback.link_error(mark_product_failed.si(product_id))
    return chord(header, callback).apply_async()


def _demo_pause():
    if settings.DEMO_STEP_DELAY:
        time.sleep(settings.DEMO_STEP_DELAY)


# --------------------------------------------------------------------------- #
# 1. CSV report
# --------------------------------------------------------------------------- #
@shared_task(bind=True, name="sales.generate_report")
def generate_report(self, report_id):
    report = ReportRequest.objects.get(pk=report_id)
    report.mark_processing()
    try:
        if report.simulate == ReportRequest.Simulate.REPORT_FAIL:
            _demo_pause()
            raise RuntimeError("Simulated failure: data warehouse connection timed out")

        qs = report.sales_queryset()
        total = qs.count()
        step = max(1, total // 20)  # ~20 progress updates

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["date", "sku", "product", "region", "units", "unit_price", "revenue"])

        written, revenue = 0, Decimal("0")
        for sale in qs.iterator(chunk_size=500):
            writer.writerow([sale.sold_at, sale.sku, sale.product_name, sale.region,
                             sale.units, sale.unit_price, sale.total])
            written += 1
            revenue += sale.total
            if written % step == 0 or written == total:
                pct = min(95, int(written / max(total, 1) * 95))
                ReportRequest.objects.filter(pk=report_id).update(progress=pct, rows_written=written)
                if not self.request.is_eager:  # shows up as the PROGRESS state in Flower
                    self.update_state(state="PROGRESS", meta={"progress": pct, "rows": written, "total": total})
                _demo_pause()

        writer.writerow([])
        writer.writerow(["TOTAL", "", "", "", "", "", revenue])

        name = f"ledgerline-sales-{report.date_from}_{report.date_to}.csv"
        report.file.save(name, ContentFile(buf.getvalue().encode("utf-8-sig")), save=False)
        ReportRequest.objects.filter(pk=report_id).update(
            file=report.file.name, status=ReportRequest.Status.DONE, progress=100,
            rows_written=written, finished_at=timezone.now(), error="")
    except Exception as exc:
        log.exception("Report %s failed", report_id)
        report.mark_failed(str(exc))
        raise  # the chain stops here, so no email is sent for a failed report
    return report_id


# --------------------------------------------------------------------------- #
# 2. HTML email - up to 3 retries, exponential backoff (base * 2**n  =>  10s, 20s, 40s)
# --------------------------------------------------------------------------- #
def backoff_delay(retries_so_far: int) -> int:
    return settings.EMAIL_RETRY_BASE_SECONDS * (2 ** retries_so_far)


def _deliver_email(report: ReportRequest):
    if report.simulate == ReportRequest.Simulate.SMTP_FAIL:
        raise smtplib.SMTPServerDisconnected("Simulated SMTP outage")
    ctx = {
        "report": report,
        "url": settings.SITE_URL + reverse("report_download", args=[report.id]),
        "status_url": settings.SITE_URL + report.get_absolute_url(),
    }
    msg = EmailMultiAlternatives(
        subject=f"Your sales report for {report.date_from:%b %d} - {report.date_to:%b %d, %Y} is ready",
        body=render_to_string("emails/report_ready.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[report.email],
    )
    msg.attach_alternative(render_to_string("emails/report_ready.html", ctx), "text/html")
    msg.send(fail_silently=False)


@shared_task(bind=True, max_retries=settings.EMAIL_MAX_RETRIES, name="sales.send_report_email")
def send_report_email(self, report_id):
    report = ReportRequest.objects.get(pk=report_id)
    if report.status != ReportRequest.Status.DONE:
        return "skipped"

    attempt = self.request.retries + 1
    ReportRequest.objects.filter(pk=report_id).update(
        email_status=ReportRequest.EmailStatus.SENDING, email_attempts=attempt, next_retry_at=None)
    try:
        _deliver_email(report)
    except (smtplib.SMTPException, OSError) as exc:   # SMTPException, ConnectionError, TimeoutError...
        if self.request.retries >= self.max_retries:
            ReportRequest.objects.filter(pk=report_id).update(
                email_status=ReportRequest.EmailStatus.FAILED, email_error=str(exc)[:500], next_retry_at=None)
            raise
        delay = backoff_delay(self.request.retries)
        ReportRequest.objects.filter(pk=report_id).update(
            email_status=ReportRequest.EmailStatus.RETRYING, email_error=str(exc)[:500],
            next_retry_at=timezone.now() + timedelta(seconds=delay))
        log.warning("Email for %s failed (attempt %s): %s - retrying in %ss", report_id, attempt, exc, delay)
        raise self.retry(exc=exc, countdown=delay)

    ReportRequest.objects.filter(pk=report_id).update(
        email_status=ReportRequest.EmailStatus.SENT, email_sent_at=timezone.now(),
        email_error="", next_retry_at=None)
    return "sent"


# --------------------------------------------------------------------------- #
# 3. Image resizing: group (3 in parallel) + chord callback
# --------------------------------------------------------------------------- #
@shared_task(bind=True, name="sales.resize_image", max_retries=3,
             autoretry_for=(OSError,), retry_backoff=2, retry_jitter=True)
def resize_image(self, product_id, label, max_px):
    Product.objects.filter(pk=product_id, state=Product.State.PENDING).update(state=Product.State.PROCESSING)
    product = Product.objects.get(pk=product_id)

    with product.original.open("rb") as fh:
        img = Image.open(fh)
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode or "transparency" in img.info else "RGB")
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)  # never upscales
        out = io.BytesIO()
        img.save(out, "WEBP", quality=82, method=4)

    variant, _ = ProductImage.objects.get_or_create(product=product, label=label)
    if variant.image:
        variant.image.delete(save=False)
    variant.image.save(f"{product.sku}-{label}.webp", ContentFile(out.getvalue()), save=False)
    variant.width, variant.height = img.size
    variant.save()
    _demo_pause()
    return {"label": label, "width": img.width, "height": img.height}


@shared_task(name="sales.mark_product_processed")
def mark_product_processed(results, product_id):
    """Chord callback: `results` is the list of the three resize_image return values."""
    Product.objects.filter(pk=product_id).update(
        state=Product.State.PROCESSED, processed_at=timezone.now(), error="")
    return {"product": product_id, "variants": sorted(r["label"] for r in results)}


@shared_task(name="sales.mark_product_failed")
def mark_product_failed(product_id):
    Product.objects.filter(pk=product_id).update(
        state=Product.State.FAILED, error="One or more image sizes could not be generated.")
