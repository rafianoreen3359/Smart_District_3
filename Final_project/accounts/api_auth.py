import hashlib
import secrets
from rest_framework import authentication, exceptions
from .models import APIKey

def hash_key(raw): return hashlib.sha256(raw.encode()).hexdigest()

def generate_api_key(name):
    raw = "th_" + secrets.token_urlsafe(32)
    APIKey.objects.create(name=name, key_hash=hash_key(raw), prefix=raw[:8])
    return raw  # show once, never stored in plain text


class APIKeyUser:
    """Lightweight principal for integrations."""
    is_authenticated = True
    is_active = True
    role = "Integration"
    pk = id = None
    def __init__(self, key): self.api_key = key
    def __str__(self): return f"apikey:{self.api_key.name}"


class APIKeyAuthentication(authentication.BaseAuthentication):
    keyword = "X-API-Key"

    def authenticate(self, request):
        raw = request.headers.get(self.keyword)
        if not raw:
            return None
        try:
            key = APIKey.objects.get(key_hash=hash_key(raw), is_active=True)
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key")
        return (APIKeyUser(key), key)

    def authenticate_header(self, request):
        return self.keyword
    # accounts/schema.py  (import it in accounts/apps.py ready())
from drf_spectacular.extensions import OpenApiAuthenticationExtension

class APIKeyScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.api_auth.APIKeyAuthentication"
    name = "ApiKeyAuth"
    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "header", "name": "X-API-Key"}