from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0015_remove_lesson_video_and_cleanup_resources"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentsubmission",
            name="file_url",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="studentsubmission",
            name="video_url",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
