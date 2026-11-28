from django.db import transaction
from django.db.models import Sum, F
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from config.celery import app as celery_app

from .forms import ProductForm, ReportRequestForm
from .models import Product, ReportRequest, Sale
from .tasks import IMAGE_SIZES, enqueue_product, enqueue_report

S = ReportRequest.Status
E = ReportRequest.EmailStatus


def home(request):
    stats = Sale.objects.aggregate(rev=Sum(F("units") * F("unit_price")), n=Sum("units"))
    return render(request, "sales/home.html", {
        "revenue": stats["rev"] or 0, "units": stats["n"] or 0,
        "reports": ReportRequest.objects.count(), "products": Product.objects.count(),
    })


# ---------------------------------------------------------------- reports --
def report_create(request):
    form = ReportRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            report = form.save()  # status=Pending
            # Only fires AFTER the commit, so the worker can never look up a row that
            # doesn't exist yet. If the transaction rolls back, nothing is queued.
            transaction.on_commit(lambda: enqueue_report(report.pk))
        return redirect(report)  # returns immediately; the worker does the heavy lifting
    return render(request, "sales/report_form.html", {"form": form})


def report_list(request):
    return render(request, "sales/report_list.html", {"reports": ReportRequest.objects.all()[:50]})


def _steps(r):
    queued = "done" if r.status != S.PENDING else "active"
    generate = {S.PENDING: "todo", S.PROCESSING: "active", S.DONE: "done", S.FAILED: "failed"}[r.status]
    if r.status in (S.PENDING, S.PROCESSING):
        email = "todo"
    elif r.status == S.FAILED:
        email = "todo"
    else:
        email = {E.NOT_SENT: "active", E.SENDING: "active", E.RETRYING: "retry",
                 E.SENT: "done", E.FAILED: "failed", E.SKIPPED: "todo"}[r.email_status]
    complete = "failed" if r.status == S.FAILED or r.email_status == E.FAILED else (
        "done" if r.is_terminal else "todo")
    hints = {
        "queued": "Saved and handed to Celery",
        "generate": f"{r.rows_written:,} rows written" if r.rows_written else "Building the CSV",
        "email": {"retrying": f"Attempt {r.email_attempts} failed - backing off",
                  "done": "Email delivered", "failed": "Gave up after 3 retries",
                  "active": f"Attempt {max(r.email_attempts, 1)}"}.get(email, "Link sent by email"),
        "complete": "Report ready to download",
    }
    return [{"key": k, "label": l, "state": s, "hint": hints[k]} for k, l, s in [
        ("queued", "Queued", queued), ("generate", "Generating CSV", generate),
        ("email", "Emailing link", email), ("complete", "Complete", complete)]]


def serialize_report(r):
    celery_state = None
    if r.task_id:
        try:
            celery_state = celery_app.AsyncResult(r.task_id).state
        except Exception:  # broker/backend hiccup must not break the status page
            celery_state = None
    return {
        "id": str(r.id), "status": r.status, "status_label": r.get_status_display(),
        "progress": r.progress, "rows": r.rows_written, "error": r.error,
        "email_status": r.email_status, "email_label": r.get_email_status_display(),
        "email_attempts": r.email_attempts, "email_error": r.email_error,
        "next_retry_at": r.next_retry_at.isoformat() if r.next_retry_at else None,
        "celery_state": celery_state, "steps": _steps(r),
        "download_url": reverse("report_download", args=[r.id]) if r.status == S.DONE else None,
        "terminal": r.is_terminal,
    }


def report_status(request, pk):
    r = get_object_or_404(ReportRequest, pk=pk)
    return render(request, "sales/report_status.html", {"r": r, "data": serialize_report(r)})


def report_status_json(request, pk):
    r = get_object_or_404(ReportRequest, pk=pk)
    return JsonResponse(serialize_report(r))


def report_download(request, pk):
    r = get_object_or_404(ReportRequest, pk=pk)
    if r.status != S.DONE or not r.file:
        raise Http404("Report is not ready")
    return FileResponse(r.file.open("rb"), as_attachment=True, filename=r.file.name.rsplit("/", 1)[-1])


# --------------------------------------------------------------- products --
def product_list(request):
    return render(request, "sales/product_list.html",
                  {"products": Product.objects.prefetch_related("variants")})


def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            product = form.save()
            transaction.on_commit(lambda: enqueue_product(product.pk))
        return redirect(product)
    return render(request, "sales/product_form.html", {"form": form})


def serialize_product(p):
    done = {v.label: v for v in p.variants.all() if v.image}
    return {
        "state": p.state, "state_label": p.get_state_display(), "error": p.error,
        "terminal": p.state in (Product.State.PROCESSED, Product.State.FAILED),
        "variants": [{"label": label, "px": px, "ready": label in done,
                      "url": done[label].image.url if label in done else None,
                      "size": f"{done[label].width}x{done[label].height}" if label in done else ""}
                     for label, px in IMAGE_SIZES.items()],
    }


def product_detail(request, pk):
    p = get_object_or_404(Product.objects.prefetch_related("variants"), pk=pk)
    return render(request, "sales/product_detail.html", {"p": p, "data": serialize_product(p)})


def product_status_json(request, pk):
    p = get_object_or_404(Product.objects.prefetch_related("variants"), pk=pk)
    return JsonResponse(serialize_product(p))
