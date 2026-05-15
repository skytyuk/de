from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


def publish_demo_lessons(apps, schema_editor):
    Roles = apps.get_model("main", "Roles")
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    StudyGroup = apps.get_model("main", "StudyGroup")
    Application = apps.get_model("main", "Application")
    Enrollment = apps.get_model("main", "Enrollment")
    Schedule = apps.get_model("main", "Schedule")
    LessonAttendance = apps.get_model("main", "LessonAttendance")
    LessonProgress = apps.get_model("main", "LessonProgress")
    Notification = apps.get_model("main", "Notification")

    now = timezone.now()

    for group in StudyGroup.objects.filter(is_active=True):
        visible_ids = list(
            Schedule.objects
            .filter(group=group)
            .order_by("start_at")
            .values_list("id", flat=True)[:4]
        )
        Schedule.objects.filter(id__in=visible_ids).update(is_visible_to_students=True)

    student_role, _ = Roles.objects.get_or_create(name="student")
    student, _ = Users.objects.get_or_create(
        email="wwataban@gmail.com",
        defaults={
            "last_name": "Ватабан",
            "first_name": "Студент",
            "middle_name": "",
            "phone": "+79993000999",
            "password": make_password("Student123!"),
            "role": student_role,
        },
    )
    course = Course.objects.filter(title__icontains="Excel").first()
    if not course:
        return

    group = StudyGroup.objects.filter(course=course, is_active=True).order_by("id").first()
    if not group:
        return

    application, _ = Application.objects.get_or_create(
        student=student,
        course=course,
        defaults={
            "status": "approved",
            "comment": "Демонстрационное зачисление на курс Excel.",
        },
    )
    Enrollment.objects.get_or_create(
        student=student,
        course=course,
        defaults={
            "group": group,
            "application": application,
            "status": "active",
        },
    )

    past_schedules = list(Schedule.objects.filter(group=group).order_by("start_at")[:2])
    for index, schedule in enumerate(past_schedules, start=1):
        schedule.start_at = now - timedelta(days=4 - index, hours=2)
        schedule.end_at = schedule.start_at + timedelta(hours=1, minutes=30)
        schedule.status = "completed"
        schedule.is_visible_to_students = True
        schedule.save(update_fields=["start_at", "end_at", "status", "is_visible_to_students", "updated_at"])

        LessonAttendance.objects.get_or_create(
            schedule=schedule,
            student=student,
            defaults={
                "status": "present",
                "joined_at": schedule.start_at,
                "left_at": schedule.end_at,
            },
        )
        if schedule.lesson:
            LessonProgress.objects.get_or_create(
                student=student,
                lesson=schedule.lesson,
                defaults={
                    "status": "completed",
                    "started_at": schedule.start_at,
                    "completed_at": schedule.end_at,
                },
            )

    Notification.objects.get_or_create(
        user=student,
        title="Открыт архив занятий",
        message='В курсе "Excel и аналитика данных" доступны прошедшие занятия.',
    )


def rollback_publish_demo_lessons(apps, schema_editor):
    Schedule = apps.get_model("main", "Schedule")
    Notification = apps.get_model("main", "Notification")

    Schedule.objects.update(is_visible_to_students=False)
    Notification.objects.filter(title="Открыт архив занятий").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0011_schedule_is_visible_to_students"),
    ]

    operations = [
        migrations.RunPython(publish_demo_lessons, rollback_publish_demo_lessons),
    ]
