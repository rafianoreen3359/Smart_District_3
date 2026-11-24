from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(is_deleted=False, deleted_at=None)


class SoftDeleteManager(models.Manager):
    def __init__(self, *args, alive_only=True, **kwargs):
        self.alive_only = alive_only
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        qs = self._queryset_class(self.model, using=self._db)
        return qs.filter(is_deleted=False) if self.alive_only else qs


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager.from_queryset(SoftDeleteQuerySet)()
    all_objects = SoftDeleteManager.from_queryset(SoftDeleteQuerySet)(alive_only=False)

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class PostQuerySet(SoftDeleteQuerySet):
    def published(self):
        return self.filter(status=Post.PUBLISHED)

    def drafts(self):
        return self.filter(status=Post.DRAFT)

    def by_author(self, user):
        return self.filter(author=user)

    def recent(self, days=7):
        return self.filter(created_at__gte=timezone.now() - timedelta(days=days))

    def with_comment_count(self):
        return self.annotate(comment_count=Count("comments", distinct=True))


PostManager = SoftDeleteManager.from_queryset(PostQuerySet)


class Post(SoftDeleteModel):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUS_CHOICES = [(DRAFT, "Draft"), (PUBLISHED, "Published")]

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PostManager()
    all_objects = PostManager(alive_only=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment on {self.post_id}"