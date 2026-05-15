from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0010_seed_more_students_and_teacher_flow"),
    ]

    operations = [
        migrations.AddField(
            model_name="schedule",
            name="is_visible_to_students",
            field=models.BooleanField(default=False),
        ),
    ]
