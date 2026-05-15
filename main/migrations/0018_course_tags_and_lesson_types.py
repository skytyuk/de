from django.db import migrations, models
import django.db.models.deletion


def migrate_course_tags(apps, schema_editor):
    Course = apps.get_model("main", "Course")
    CourseTag = apps.get_model("main", "CourseTag")
    CourseTagRelation = apps.get_model("main", "CourseTagRelation")

    for course in Course.objects.exclude(tags__isnull=True).exclude(tags=""):
        tag_names = [
            tag.strip()
            for tag in (course.tags or "").split(",")
            if tag.strip()
        ]
        for tag_name in tag_names:
            tag, _ = CourseTag.objects.get_or_create(name=tag_name)
            CourseTagRelation.objects.get_or_create(course=course, tag=tag)


def normalize_lesson_types(apps, schema_editor):
    Lesson = apps.get_model("main", "Lesson")
    Lesson.objects.exclude(lesson_type="offline").update(lesson_type="online")


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0017_material_type_without_text"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseTag",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Course tag",
                "verbose_name_plural": "Course tags",
                "db_table": "course_tags",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CourseTagRelation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_tag_relations",
                        to="main.course",
                    ),
                ),
                (
                    "tag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_relations",
                        to="main.coursetag",
                    ),
                ),
            ],
            options={
                "verbose_name": "Course tag relation",
                "verbose_name_plural": "Course tag relations",
                "db_table": "course_tag_relations",
            },
        ),
        migrations.AddConstraint(
            model_name="coursetagrelation",
            constraint=models.UniqueConstraint(fields=("course", "tag"), name="unique_course_tag_relation"),
        ),
        migrations.RunPython(migrate_course_tags, migrations.RunPython.noop),
        migrations.RunPython(normalize_lesson_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="course",
            name="image",
        ),
        migrations.RemoveField(
            model_name="course",
            name="tags",
        ),
        migrations.AddField(
            model_name="course",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                related_name="courses",
                through="main.CourseTagRelation",
                to="main.coursetag",
            ),
        ),
        migrations.AlterField(
            model_name="lesson",
            name="lesson_type",
            field=models.CharField(
                choices=[
                    ("online", "Онлайн-занятие"),
                    ("offline", "Оффлайн-занятие"),
                ],
                default="online",
                max_length=50,
            ),
        ),
    ]
