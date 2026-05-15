import re

from django.db import migrations
from django.db.models import Q


USER_OBJECT_PATTERN = re.compile(r"Users object \((\d+)\)")


def user_label(user):
    parts = [
        (getattr(user, "last_name", "") or "").strip(),
        (getattr(user, "first_name", "") or "").strip(),
        (getattr(user, "middle_name", "") or "").strip(),
    ]
    full_name = " ".join(part for part in parts if part)
    return full_name or getattr(user, "email", "") or f"Пользователь #{user.pk}"


def cleanup_resources_and_notifications(apps, schema_editor):
    Material = apps.get_model("main", "Material")
    Assignment = apps.get_model("main", "Assignment")
    Notification = apps.get_model("main", "Notification")
    Users = apps.get_model("main", "Users")

    missing_resource = (Q(file="") | Q(file__isnull=True)) & (Q(file_url="") | Q(file_url__isnull=True))

    for material in Material.objects.filter(missing_resource):
        material.file_url = f"https://example.com/materials/{material.pk}"
        material.save(update_fields=["file_url"])

    for assignment in Assignment.objects.filter(missing_resource):
        assignment.file_url = f"https://example.com/assignments/{assignment.pk}"
        assignment.save(update_fields=["file_url", "updated_at"])

    users_cache = {}

    def replace_user_object(match):
        user_id = int(match.group(1))
        if user_id not in users_cache:
            users_cache[user_id] = Users.objects.filter(pk=user_id).first()
        user = users_cache[user_id]
        return user_label(user) if user else f"Пользователь #{user_id}"

    for notification in Notification.objects.filter(message__contains="Users object ("):
        notification.message = USER_OBJECT_PATTERN.sub(replace_user_object, notification.message)
        notification.save(update_fields=["message"])

    for notification in Notification.objects.filter(title__contains="Users object ("):
        notification.title = USER_OBJECT_PATTERN.sub(replace_user_object, notification.title)
        notification.save(update_fields=["title"])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0014_excel_groups_tests_and_resources"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="lesson",
            name="video_url",
        ),
        migrations.RunPython(cleanup_resources_and_notifications, migrations.RunPython.noop),
    ]
