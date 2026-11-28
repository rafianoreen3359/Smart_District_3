import uuid
from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone

REGIONS = [
    ("NA", "North America"),
    ("EMEA", "Europe, Middle East & Africa"),
    ("APAC", "Asia-Pacific"),
    ("LATAM", "Latin America"),
]


class Sale(models.Model):
    """Source rows for the CSV report."""
    sku = models.CharField(max_length=32)
    product_name = models.CharField(max_length=120)
    region = models.CharField(max_length=8, choices=REGIONS)
    units = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sold_at = models.DateField(db_index=True)

    @property
    def total(self) -> Decimal:
        return self.units * self.unit_price


class ReportRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class EmailStatus(models.TextChoices):
        NOT_SENT = "not_sent", "Waiting"
        SENDING = "sending", "Sending"
        RETRYING = "retrying", "Retrying"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    class Simulate(models.TextChoices):
        NONE = "", "No - run normally"
        REPORT_FAIL = "report_fail", "Make the report task fail"
        SMTP_FAIL = "smtp_fail", "Make SMTP fail (exercise retries)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester_name = models.CharField(max_length=80)
    email = models.EmailField()
    date_from = models.DateField()
    date_to = models.DateField()
    region = models.CharField(max_length=8, choices=[("ALL", "All regions")] + REGIONS, default="ALL")
    simulate = models.CharField(max_length=16, choices=Simulate.choices, blank=True, default="")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    rows_written = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    file = models.FileField(upload_to="reports/%Y/%m/", blank=True)

    task_id = models.CharField(max_length=64, blank=True)
    email_task_id = models.CharField(max_length=64, blank=True)
    email_status = models.CharField(max_length=10, choices=EmailStatus.choices, default=EmailStatus.NOT_SENT)
    email_attempts = models.PositiveSmallIntegerField(default=0)
    email_error = models.TextField(blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report {str(self.id)[:8]} ({self.status})"

    def get_absolute_url(self):
        return reverse("report_status", args=[self.id])

    @property
    def is_terminal(self) -> bool:
        if self.status == self.Status.FAILED:
            return True
        return self.status == self.Status.DONE and self.email_status in (
            self.EmailStatus.SENT, self.EmailStatus.FAILED)

    def sales_queryset(self):
        qs = Sale.objects.filter(sold_at__range=(self.date_from, self.date_to)).order_by("sold_at", "id")
        if self.region != "ALL":
            qs = qs.filter(region=self.region)
        return qs

    # Status transitions use .update() so they never clobber fields written by the other task.
    def _update(self, **fields):
        type(self).objects.filter(pk=self.pk).update(**fields)

    def mark_processing(self):
        self._update(status=self.Status.PROCESSING, started_at=timezone.now(), progress=1)

    def mark_failed(self, message: str):
        self._update(status=self.Status.FAILED, error=message[:2000], finished_at=timezone.now(),
                     email_status=self.EmailStatus.SKIPPED)


class Product(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=120)
    sku = models.SlugField(max_length=32, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original = models.ImageField(upload_to="products/originals/")
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING, db_index=True)
    error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def get_absolute_url(self):
        return reverse("product_detail", args=[self.pk])

    def variant(self, label):
        return next((v for v in self.variants.all() if v.label == label), None)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField(max_length=16)
    image = models.ImageField(upload_to="products/variants/", blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("product", "label")]
