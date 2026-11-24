"""Data migration: create the Viewer, Editor and Reviewer groups with their permissions."""
from django.db import migrations

GROUP_PERMISSIONS = {
    "Viewer": ["view_document"],
    "Editor": ["view_document", "add_document", "change_document"],
    "Reviewer": ["view_document", "change_document", "publish_document", "archive_document"],
}

PERMISSION_NAMES = {
    "view_document": "Can view document",
    "add_document": "Can add document",
    "change_document": "Can change document",
    "publish_document": "Can publish document",
    "archive_document": "Can archive document",
}


def create_groups(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    # Permissions are normally created after migrate; create what we need right now.
    content_type, _ = ContentType.objects.get_or_create(app_label="documents", model="document")

    for group_name, codenames in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = []
        for codename in codenames:
            permission, _ = Permission.objects.get_or_create(
                content_type=content_type,
                codename=codename,
                defaults={"name": PERMISSION_NAMES[codename]},
            )
            permissions.append(permission)
        group.permissions.set(permissions)


def delete_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GROUP_PERMISSIONS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
        ("auth", "__latest__"),
        ("contenttypes", "__latest__"),
    ]

    operations = [
        migrations.RunPython(create_groups, delete_groups),
    ]
