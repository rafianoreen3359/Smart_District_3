from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from documents.models import Document


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT with custom claims: role and email (plus username)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["username"] = user.username
        return token


class DocumentSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = Document
        fields = ["id", "title", "content", "status", "owner", "owner_email", "created_at", "updated_at"]
        # status changes only through the publish / archive actions
        read_only_fields = ["status", "owner", "created_at", "updated_at"]
