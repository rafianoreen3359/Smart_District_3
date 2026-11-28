from rest_framework import serializers
from .models import Project, Membership

class ProjectSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    task_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Project
        fields = ["id", "name", "description", "owner", "owner_email", "task_count", "created_at"]
        read_only_fields = ["owner", "created_at"]

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "project", "user"]