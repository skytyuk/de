from django.db import migrations, models


def fill_schedule_codes(apps, schema_editor):
    Schedule = apps.get_model("main", "Schedule")

    for schedule in Schedule.objects.filter(meeting_code__isnull=True):
        schedule.meeting_code = f"AE-{schedule.id:04d}"
        schedule.save(update_fields=["meeting_code"])


def rollback_schedule_codes(apps, schema_editor):
    Schedule = apps.get_model("main", "Schedule")
    Schedule.objects.update(meeting_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0012_publish_demo_lessons_for_students"),
    ]

    operations = [
        migrations.AddField(
            model_name="assignment",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="assignments/"),
        ),
        migrations.AddField(
            model_name="assignment",
            name="file_url",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="schedule",
            name="meeting_code",
            field=models.CharField(blank=True, max_length=80, null=True),
        ),
        migrations.RunPython(fill_schedule_codes, rollback_schedule_codes),
    ]
