from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import APIKey


class ActiveJWTAuthentication(JWTAuthentication):
    """Normal JWT auth, but a locked account's tokens stop working immediately."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.is_locked:
            raise AuthenticationFailed("This account is locked.", code="account_locked")
        return user


class APIKeyAuthentication(BaseAuthentication):
    """Header:  Authorization: Api-Key <key>

    request.user is the key's owner and request.auth is the APIKey object.
    """

    keyword = b"api-key"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None  # not an API-key request; let the next authenticator try
        if len(parts) != 2:
            raise AuthenticationFailed("Invalid API key header. Use: Authorization: Api-Key <key>")
        try:
            raw_key = parts[1].decode("utf-8")
        except UnicodeError:
            raise AuthenticationFailed("Invalid API key.")

        key = APIKey.authenticate_raw(raw_key)
        if key is None:
            raise AuthenticationFailed("Invalid or revoked API key.")
        return (key.owner, key)

    def authenticate_header(self, request):
        return "Api-Key"
