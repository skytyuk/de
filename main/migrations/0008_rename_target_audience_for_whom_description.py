from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0007_enrich_courses_modules_teachers"),
    ]

    operations = [
        migrations.RenameField(
            model_name="course",
            old_name="target_audience",
            new_name="for_whom_description",
        ),
        migrations.AlterField(
            model_name="course",
            name="for_whom_description",
            field=models.TextField(
                "Описание для кого сделан курс",
                blank=True,
                null=True,
            ),
        ),
    ]
