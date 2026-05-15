from django.db import migrations, models


def move_text_materials_to_links(apps, schema_editor):
    Material = apps.get_model("main", "Material")
    Material.objects.filter(material_type="text").update(material_type="link")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0016_student_submission_links"),
    ]

    operations = [
        migrations.RunPython(move_text_materials_to_links, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="material",
            name="material_type",
            field=models.CharField(
                choices=[
                    ("file", "Файл"),
                    ("link", "Ссылка"),
                    ("video", "Видео"),
                ],
                default="file",
                max_length=50,
            ),
        ),
    ]
