from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def add_excel_groups_tests_and_resources(apps, schema_editor):
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    CourseTeacher = apps.get_model("main", "CourseTeacher")
    StudyGroup = apps.get_model("main", "StudyGroup")
    Lesson = apps.get_model("main", "Lesson")
    Schedule = apps.get_model("main", "Schedule")
    Assignment = apps.get_model("main", "Assignment")
    Test = apps.get_model("main", "Test")
    TestQuestion = apps.get_model("main", "TestQuestion")
    TestAnswer = apps.get_model("main", "TestAnswer")

    course = Course.objects.filter(title__icontains="Excel").first()
    if not course:
        return

    teachers = list(Users.objects.filter(role__name="teacher").order_by("id")[:4])
    if not teachers:
        return

    today = timezone.localdate()
    for index, teacher in enumerate(teachers, start=1):
        CourseTeacher.objects.get_or_create(course=course, teacher=teacher)
        group, _ = StudyGroup.objects.get_or_create(
            course=course,
            name=f"{course.title} - поток {index}",
            defaults={
                "teacher": teacher,
                "start_date": today + timedelta(days=index * 5),
                "end_date": today + timedelta(days=90 + index * 5),
                "max_students": 16,
                "is_active": True,
            },
        )
        if group.teacher_id != teacher.id:
            group.teacher = teacher
            group.save(update_fields=["teacher", "updated_at"])

        lessons = list(Lesson.objects.filter(module__course=course).order_by("module__sort_order", "sort_order")[:3])
        for lesson_index, lesson in enumerate(lessons, start=1):
            start_at = timezone.now() + timedelta(days=index * 4 + lesson_index)
            schedule, _ = Schedule.objects.get_or_create(
                group=group,
                lesson=lesson,
                start_at=start_at,
                defaults={
                    "teacher": teacher,
                    "end_at": start_at + timedelta(hours=1, minutes=30),
                    "meeting_link": "",
                    "meeting_code": f"EXCEL-{index}{lesson_index}",
                    "is_visible_to_students": lesson_index <= 2,
                    "status": "planned",
                },
            )
            if not schedule.meeting_code:
                schedule.meeting_code = f"EXCEL-{index}{lesson_index}"
                schedule.save(update_fields=["meeting_code"])

    for assignment in Assignment.objects.filter(lesson__module__course=course):
        if not assignment.file_url:
            assignment.file_url = "https://example.com/excel-assignment-template.xlsx"
            assignment.save(update_fields=["file_url", "updated_at"])

    for lesson in Lesson.objects.filter(module__course=course):
        test, _ = Test.objects.get_or_create(
            lesson=lesson,
            title=f"Проверка знаний: {lesson.title}",
            defaults={
                "description": "Короткий тест по Excel и аналитике данных.",
                "passing_score": 70,
                "max_attempts": 2,
            },
        )
        if not TestQuestion.objects.filter(test=test).exists():
            question = TestQuestion.objects.create(
                test=test,
                question_text="Какая функция помогает быстро посчитать сумму диапазона?",
                question_type="single",
                score=50,
                sort_order=1,
            )
            TestAnswer.objects.create(question=question, answer_text="SUM", is_correct=True)
            TestAnswer.objects.create(question=question, answer_text="TEXT", is_correct=False)
            question = TestQuestion.objects.create(
                test=test,
                question_text="Что используют для группировки и анализа больших таблиц?",
                question_type="single",
                score=50,
                sort_order=2,
            )
            TestAnswer.objects.create(question=question, answer_text="Сводную таблицу", is_correct=True)
            TestAnswer.objects.create(question=question, answer_text="Границу ячейки", is_correct=False)


def rollback_excel_groups_tests_and_resources(apps, schema_editor):
    Course = apps.get_model("main", "Course")
    StudyGroup = apps.get_model("main", "StudyGroup")
    Test = apps.get_model("main", "Test")
    Assignment = apps.get_model("main", "Assignment")

    course = Course.objects.filter(title__icontains="Excel").first()
    if not course:
        return

    StudyGroup.objects.filter(course=course, name__contains=" - поток ").delete()
    Test.objects.filter(lesson__module__course=course, title__startswith="Проверка знаний:").delete()
    Assignment.objects.filter(lesson__module__course=course, file_url="https://example.com/excel-assignment-template.xlsx").update(file_url=None)


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0013_schedule_code_assignment_files"),
    ]

    operations = [
        migrations.RunPython(add_excel_groups_tests_and_resources, rollback_excel_groups_tests_and_resources),
    ]
