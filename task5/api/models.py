import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_key(raw_key):
    """SHA-256 is right for API keys: they are long random strings, not human passwords."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKey(models.Model):
    """A service-integration key. Only the hash is stored; the raw key is shown once."""

    READ_SCOPE = "documents:read"

    name = models.CharField(max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys")
    prefix = models.CharField(max_length=12, db_index=True, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    scopes = models.CharField(
        max_length=200, default=READ_SCOPE, help_text="Space-separated scopes. API keys are always read-only."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API key"

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    # ---- creating ----
    @staticmethod
    def generate_raw():
        return secrets.token_urlsafe(32)

    def set_key(self, raw_key):
        self.prefix = raw_key[:8]
        self.key_hash = hash_key(raw_key)

    @classmethod
    def create_with_key(cls, name, owner, scopes=READ_SCOPE):
        """Return (api_key, raw_key). The raw key is not stored anywhere."""
        raw = cls.generate_raw()
        key = cls(name=name, owner=owner, scopes=scopes)
        key.set_key(raw)
        key.save()
        return key, raw

    # ---- checking ----
    @classmethod
    def authenticate_raw(cls, raw_key):
        if not raw_key or len(raw_key) < 8:
            return None
        digest = hash_key(raw_key)
        candidates = cls.objects.select_related("owner").filter(prefix=raw_key[:8], revoked_at__isnull=True)
        for key in candidates:
            if hmac.compare_digest(key.key_hash, digest) and key.is_usable:
                cls.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
                return key
        return None

    @property
    def is_active(self):
        return self.revoked_at is None

    @property
    def is_usable(self):
        owner = self.owner
        return self.is_active and owner.is_active and not owner.is_locked

    def has_scope(self, scope):
        return scope in self.scopes.split()

    def revoke(self):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])
