from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import DocumentForm
from .mixins import OwnerOrReviewerRequiredMixin
from .models import Document


class DocumentListView(PermissionRequiredMixin, ListView):
    permission_required = "documents.view_document"
    template_name = "documents/document_list.html"
    context_object_name = "documents"

    def get_queryset(self):
        queryset = Document.objects.select_related("owner")
        status = self.request.GET.get("status")
        if status in Document.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = Document.objects.aggregate(
            total=Count("id"),
            drafts=Count("id", filter=Q(status=Document.Status.DRAFT)),
            published=Count("id", filter=Q(status=Document.Status.PUBLISHED)),
            archived=Count("id", filter=Q(status=Document.Status.ARCHIVED)),
        )
        context["current_status"] = self.request.GET.get("status", "")
        return context


class DocumentDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "documents.view_document"
    queryset = Document.objects.select_related("owner")
    template_name = "documents/document_detail.html"
    context_object_name = "document"


class DocumentCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "documents.add_document"
    model = Document
    form_class = DocumentForm
    template_name = "documents/document_form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, "Document created.")
        return super().form_valid(form)


class DocumentUpdateView(PermissionRequiredMixin, OwnerOrReviewerRequiredMixin, UpdateView):
    permission_required = "documents.change_document"   # model-level permission
    model = Document                                    # + owner-or-reviewer check from the mixin
    form_class = DocumentForm
    template_name = "documents/document_form.html"

    def form_valid(self, form):
        messages.success(self.request, "Document updated.")
        return super().form_valid(form)


class StatusChangeView(PermissionRequiredMixin, View):
    """Base for the publish / archive buttons (POST only)."""

    http_method_names = ["post"]
    new_status = None
    allowed_from = ()
    success_message = ""

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk)
        if document.status not in self.allowed_from:
            messages.warning(request, f"This document is already {document.get_status_display().lower()}.")
        else:
            document.status = self.new_status
            document.save(update_fields=["status", "updated_at"])
            messages.success(request, self.success_message)
        return redirect(document)


class DocumentPublishView(StatusChangeView):
    permission_required = "documents.publish_document"
    new_status = Document.Status.PUBLISHED
    allowed_from = (Document.Status.DRAFT,)
    success_message = "Document published."


class DocumentArchiveView(StatusChangeView):
    permission_required = "documents.archive_document"
    new_status = Document.Status.ARCHIVED
    allowed_from = (Document.Status.DRAFT, Document.Status.PUBLISHED)
    success_message = "Document archived."
