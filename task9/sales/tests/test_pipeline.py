import io
import shutil
import smtplib
import tempfile
from datetime import date
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from config.celery import app as celery_app
from sales import tasks
from sales.models import Product, ReportRequest, Sale

TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP_MEDIA, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   EMAIL_RETRY_BASE_SECONDS=10)
class PipelineTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        celery_app.conf.task_always_eager = True      # run tasks in-process, no broker needed

    @classmethod
    def tearDownClass(cls):
        celery_app.conf.task_always_eager = False
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Sale.objects.bulk_create([
            Sale(sku="A", product_name="Alpha", region="NA", units=2, unit_price="10.00", sold_at=date(2026, 1, 5)),
            Sale(sku="B", product_name="Beta", region="EMEA", units=1, unit_price="99.50", sold_at=date(2026, 1, 9)),
        ])
        self.report = ReportRequest.objects.create(
            requester_name="Sam", email="sam@example.com", date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))

    # -- view only queues AFTER commit -------------------------------------
    def test_view_queues_on_commit_only(self):
        payload = {"requester_name": "Sam", "email": "s@example.com", "date_from": "2026-01-01",
                   "date_to": "2026-01-31", "region": "ALL", "simulate": ""}
        with mock.patch("sales.views.enqueue_report") as enq:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                resp = self.client.post(reverse("report_create"), payload)
            self.assertEqual(resp.status_code, 302)
            enq.assert_not_called()          # nothing queued until the transaction commits
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            enq.assert_called_once()

    # -- CSV + status transitions + chain ----------------------------------
    def test_chain_generates_csv_then_sends_html_email(self):
        with mock.patch.object(ReportRequest, "mark_processing", autospec=True,
                               side_effect=ReportRequest.mark_processing) as mp:
            tasks.enqueue_report(self.report.pk)
            mp.assert_called_once()
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "done")
        self.assertEqual(self.report.rows_written, 2)
        self.assertEqual(self.report.email_status, "sent")
        content = self.report.file.read().decode("utf-8-sig")
        self.assertIn("Beta", content)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn(str(self.report.id), html)   # download link is in the HTML body

    def test_failed_report_marks_failed_and_skips_email(self):
        self.report.simulate = "report_fail"
        self.report.save()
        tasks.enqueue_report(self.report.pk)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "failed")
        self.assertEqual(self.report.email_status, "skipped")
        self.assertEqual(len(mail.outbox), 0)

    # -- retries ------------------------------------------------------------
    def test_backoff_is_exponential(self):
        self.assertEqual([tasks.backoff_delay(n) for n in range(3)], [10, 20, 40])

    def test_email_retries_three_times_then_fails(self):
        tasks.generate_report.apply(args=[str(self.report.pk)])
        with mock.patch("sales.tasks.EmailMultiAlternatives.send", side_effect=smtplib.SMTPServerDisconnected("down")):
            tasks.send_report_email.apply(args=[str(self.report.pk)])
        self.report.refresh_from_db()
        self.assertEqual(self.report.email_attempts, 4)      # 1 try + 3 retries
        self.assertEqual(self.report.email_status, "failed")

    def test_email_recovers_after_transient_error(self):
        tasks.generate_report.apply(args=[str(self.report.pk)])
        real_send = tasks.EmailMultiAlternatives.send
        calls = {"n": 0}

        def flaky(self_msg, *a, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                raise smtplib.SMTPServerDisconnected("blip")
            return real_send(self_msg, *a, **kw)

        with mock.patch("sales.tasks.EmailMultiAlternatives.send", autospec=True, side_effect=flaky):
            tasks.send_report_email.apply(args=[str(self.report.pk)])
        self.report.refresh_from_db()
        self.assertEqual(self.report.email_status, "sent")
        self.assertEqual(self.report.email_attempts, 3)

    # -- group + chord ------------------------------------------------------
    def test_images_resized_in_group_and_chord_marks_processed(self):
        buf = io.BytesIO()
        Image.new("RGB", (2000, 1500), "navy").save(buf, "PNG")
        product = Product.objects.create(
            name="Pack", sku="pack-1", price="10.00",
            original=SimpleUploadedFile("pack.png", buf.getvalue(), content_type="image/png"))
        tasks.enqueue_product(product.pk)
        product.refresh_from_db()
        self.assertEqual(product.state, "processed")
        sizes = {v.label: max(v.width, v.height) for v in product.variants.all()}
        self.assertEqual(sizes, {"thumb": 150, "medium": 480, "large": 1024})

    # -- JSON endpoint ------------------------------------------------------
    def test_status_json(self):
        with mock.patch("sales.views.celery_app.AsyncResult"):
            data = self.client.get(reverse("report_status_json", args=[self.report.id])).json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual([s["key"] for s in data["steps"]], ["queued", "generate", "email", "complete"])
