from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


DEMO_ADMIN_EMAIL = "demo.admin@example.com"
DEMO_STUDENT_EMAIL = "demo.student@example.com"
DEMO_STUDENT_PHONE = "+79993000001"
DEMO_ADMIN_PHONE = "+79993000002"


def aware_datetime(day, hour, minute=0):
    value = datetime.combine(day, time(hour, minute))
    return timezone.make_aware(value, timezone.get_current_timezone())


def get_teacher_for_course(CourseTeacher, Users, course):
    relation = CourseTeacher.objects.filter(course=course).select_related("teacher").first()
    if relation:
        return relation.teacher
    return Users.objects.filter(role__name="teacher").order_by("id").first()


def seed_learning_process(apps, schema_editor):
    Roles = apps.get_model("main", "Roles")
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    CourseTeacher = apps.get_model("main", "CourseTeacher")
    StudyGroup = apps.get_model("main", "StudyGroup")
    CourseModule = apps.get_model("main", "CourseModule")
    Lesson = apps.get_model("main", "Lesson")
    Material = apps.get_model("main", "Material")
    Application = apps.get_model("main", "Application")
    Enrollment = apps.get_model("main", "Enrollment")
    TeacherAvailability = apps.get_model("main", "TeacherAvailability")
    Schedule = apps.get_model("main", "Schedule")
    ScheduleChange = apps.get_model("main", "ScheduleChange")
    LessonAttendance = apps.get_model("main", "LessonAttendance")
    Assignment = apps.get_model("main", "Assignment")
    StudentSubmission = apps.get_model("main", "StudentSubmission")
    Test = apps.get_model("main", "Test")
    TestQuestion = apps.get_model("main", "TestQuestion")
    TestAnswer = apps.get_model("main", "TestAnswer")
    TestAttempt = apps.get_model("main", "TestAttempt")
    StudentTestAnswer = apps.get_model("main", "StudentTestAnswer")
    LessonProgress = apps.get_model("main", "LessonProgress")
    LessonComment = apps.get_model("main", "LessonComment")
    Payment = apps.get_model("main", "Payment")
    Certificate = apps.get_model("main", "Certificate")
    Notification = apps.get_model("main", "Notification")
    CourseReview = apps.get_model("main", "CourseReview")
    SupportTicket = apps.get_model("main", "SupportTicket")
    SupportMessage = apps.get_model("main", "SupportMessage")

    student_role, _ = Roles.objects.get_or_create(name="student")
    admin_role, _ = Roles.objects.get_or_create(name="admin")

    demo_student, _ = Users.objects.get_or_create(
        email=DEMO_STUDENT_EMAIL,
        defaults={
            "last_name": "Демин",
            "first_name": "Студент",
            "middle_name": "Иванович",
            "phone": DEMO_STUDENT_PHONE,
            "password": make_password("Student123!"),
            "role": student_role,
        },
    )
    demo_admin, _ = Users.objects.get_or_create(
        email=DEMO_ADMIN_EMAIL,
        defaults={
            "last_name": "Админов",
            "first_name": "Админ",
            "middle_name": "Системный",
            "phone": DEMO_ADMIN_PHONE,
            "password": make_password("Admin123!"),
            "role": admin_role,
        },
    )

    today = timezone.localdate()
    courses = list(Course.objects.filter(is_active=True).order_by("id"))
    teachers = list(Users.objects.filter(role__name="teacher").order_by("id"))

    for teacher in teachers:
        for day_of_week in (1, 3, 5):
            TeacherAvailability.objects.get_or_create(
                teacher=teacher,
                day_of_week=day_of_week,
                start_time=time(18, 0),
                end_time=time(20, 30),
            )

    created_groups = []
    for course_index, course in enumerate(courses):
        teacher = get_teacher_for_course(CourseTeacher, Users, course)
        group, _ = StudyGroup.objects.get_or_create(
            course=course,
            name=f"{course.title} - группа 1",
            defaults={
                "teacher": teacher,
                "start_date": today + timedelta(days=7 + course_index),
                "end_date": today + timedelta(days=97 + course_index),
                "max_students": 18,
                "is_active": True,
            },
        )
        if teacher and group.teacher_id != teacher.id:
            group.teacher = teacher
            group.save(update_fields=["teacher", "updated_at"])
        created_groups.append(group)

        modules = list(CourseModule.objects.filter(course=course).order_by("sort_order", "id"))
        for module in modules:
            for lesson_order, lesson_kind in enumerate(("online", "text"), start=1):
                lesson, _ = Lesson.objects.get_or_create(
                    module=module,
                    title=f"{module.title}: занятие {lesson_order}",
                    defaults={
                        "description": "Учебное занятие с материалами, практикой и проверкой результата.",
                        "lesson_type": lesson_kind,
                        "video_url": "https://example.com/mobile-lesson",
                        "content": "Краткий конспект темы и список действий для мобильного приложения.",
                        "sort_order": lesson_order,
                    },
                )
                Material.objects.get_or_create(
                    lesson=lesson,
                    title=f"Конспект: {lesson.title}",
                    defaults={
                        "description": "Основной материал занятия для самостоятельного изучения.",
                        "material_type": "text",
                        "text_content": "Материал доступен в мобильном приложении и синхронизируется с Django.",
                    },
                )
                Material.objects.get_or_create(
                    lesson=lesson,
                    title=f"Ссылка на практику: {lesson.title}",
                    defaults={
                        "description": "Практическая часть занятия.",
                        "material_type": "link",
                        "file_url": "https://example.com/practice",
                    },
                )

                if lesson_order == 1:
                    Assignment.objects.get_or_create(
                        lesson=lesson,
                        title=f"Практическое задание: {module.title}",
                        defaults={
                            "description": "Выполните практику в мобильном приложении и отправьте результат на проверку.",
                            "max_score": 100,
                            "deadline": timezone.now() + timedelta(days=14 + module.sort_order),
                        },
                    )
                else:
                    test, _ = Test.objects.get_or_create(
                        lesson=lesson,
                        title=f"Тест по модулю: {module.title}",
                        defaults={
                            "description": "Проверка ключевых знаний модуля.",
                            "passing_score": 70,
                            "max_attempts": 2,
                        },
                    )
                    for question_order in (1, 2):
                        question, _ = TestQuestion.objects.get_or_create(
                            test=test,
                            sort_order=question_order,
                            defaults={
                                "question_text": f"Контрольный вопрос {question_order} по теме «{module.title}».",
                                "question_type": "single",
                                "score": 50,
                            },
                        )
                        TestAnswer.objects.get_or_create(
                            question=question,
                            answer_text="Верный вариант",
                            defaults={"is_correct": True},
                        )
                        TestAnswer.objects.get_or_create(
                            question=question,
                            answer_text="Неверный вариант",
                            defaults={"is_correct": False},
                        )

        course_lessons = list(
            Lesson.objects
            .filter(module__course=course)
            .select_related("module")
            .order_by("module__sort_order", "sort_order")[:8]
        )
        for lesson_index, lesson in enumerate(course_lessons):
            start_day = today + timedelta(days=8 + course_index + lesson_index * 3)
            start_at = aware_datetime(start_day, 18)
            end_at = aware_datetime(start_day, 19, 30)
            Schedule.objects.get_or_create(
                group=group,
                lesson=lesson,
                start_at=start_at,
                defaults={
                    "teacher": group.teacher,
                    "end_at": end_at,
                    "meeting_link": f"https://meet.example.com/course-{course.id}-lesson-{lesson.id}",
                    "status": "planned",
                },
            )

    for course_index, course in enumerate(courses[:3]):
        group = created_groups[course_index]
        status = "approved" if course_index < 2 else "new"
        application, _ = Application.objects.get_or_create(
            student=demo_student,
            course=course,
            defaults={
                "status": status,
                "comment": "Демонстрационная заявка для дипломного сценария.",
            },
        )
        if course_index < 2:
            enrollment, _ = Enrollment.objects.get_or_create(
                student=demo_student,
                course=course,
                defaults={
                    "group": group,
                    "application": application,
                    "status": "active",
                },
            )
            if enrollment.group_id != group.id:
                enrollment.group = group
                enrollment.save(update_fields=["group"])
            Payment.objects.get_or_create(
                student=demo_student,
                course=course,
                amount=course.price or Decimal("0.00"),
                defaults={
                    "status": "paid",
                    "payment_method": "Демо-оплата",
                    "paid_at": timezone.now(),
                },
            )

    first_course = courses[0] if courses else None
    if first_course:
        first_lessons = list(
            Lesson.objects
            .filter(module__course=first_course)
            .order_by("module__sort_order", "sort_order")[:5]
        )
        for index, lesson in enumerate(first_lessons):
            LessonProgress.objects.get_or_create(
                student=demo_student,
                lesson=lesson,
                defaults={
                    "status": "completed" if index < 3 else "in_progress",
                    "started_at": timezone.now() - timedelta(days=5 - index),
                    "completed_at": timezone.now() - timedelta(days=4 - index) if index < 3 else None,
                },
            )

        first_assignment = Assignment.objects.filter(lesson__module__course=first_course).order_by("id").first()
        if first_assignment:
            StudentSubmission.objects.get_or_create(
                assignment=first_assignment,
                student=demo_student,
                defaults={
                    "answer_text": "Демонстрационный ответ студента.",
                    "score": 92,
                    "feedback": "Отличная работа, можно добавить больше пояснений в выводах.",
                    "status": "checked",
                    "checked_at": timezone.now(),
                },
            )
            Notification.objects.get_or_create(
                user=demo_student,
                title="Оценка за задание",
                message=f'За задание "{first_assignment.title}" выставлено 92/100.',
            )

        first_test = Test.objects.filter(lesson__module__course=first_course).order_by("id").first()
        if first_test:
            attempt, _ = TestAttempt.objects.get_or_create(
                test=first_test,
                student=demo_student,
                defaults={
                    "score": 85,
                    "status": "passed",
                    "finished_at": timezone.now(),
                },
            )
            for question in TestQuestion.objects.filter(test=first_test):
                answer = TestAnswer.objects.filter(question=question, is_correct=True).first()
                if answer:
                    StudentTestAnswer.objects.get_or_create(
                        attempt=attempt,
                        question=question,
                        defaults={"answer": answer},
                    )
            Notification.objects.get_or_create(
                user=demo_student,
                title="Результат теста",
                message=f'Тест "{first_test.title}" пройден на 85%.',
            )

        first_schedule = Schedule.objects.filter(group__course=first_course).order_by("start_at").first()
        if first_schedule:
            LessonAttendance.objects.get_or_create(
                schedule=first_schedule,
                student=demo_student,
                defaults={
                    "status": "present",
                    "joined_at": first_schedule.start_at,
                    "left_at": first_schedule.end_at,
                },
            )
            ScheduleChange.objects.get_or_create(
                schedule=first_schedule,
                changed_by=demo_admin,
                defaults={
                    "old_start_at": first_schedule.start_at - timedelta(hours=1),
                    "old_end_at": first_schedule.end_at - timedelta(hours=1),
                    "new_start_at": first_schedule.start_at,
                    "new_end_at": first_schedule.end_at,
                    "reason": "Демонстрация переноса занятия администратором.",
                },
            )
            Notification.objects.get_or_create(
                user=demo_student,
                title="Скоро занятие",
                message=f'Ближайшее занятие по курсу "{first_course.title}" состоится {timezone.localtime(first_schedule.start_at).strftime("%d.%m.%Y %H:%M")}.',
            )

        CourseReview.objects.get_or_create(
            student=demo_student,
            course=first_course,
            defaults={
                "rating": 5,
                "comment": "Понятная структура, удобно отслеживать занятия и задания.",
            },
        )
        Certificate.objects.get_or_create(
            student=demo_student,
            course=first_course,
            defaults={"certificate_number": "DEMO-2026-0001"},
        )
        if first_lessons:
            LessonComment.objects.get_or_create(
                lesson=first_lessons[0],
                user=demo_student,
                defaults={"text": "Вопрос по практической части: где посмотреть пример решения?"},
            )

    ticket, _ = SupportTicket.objects.get_or_create(
        user=demo_student,
        subject="Не открывается материал в мобильном приложении",
        defaults={"status": "in_progress"},
    )
    SupportMessage.objects.get_or_create(
        ticket=ticket,
        sender=demo_student,
        message="Материал занятия не открывается после обновления приложения.",
    )
    SupportMessage.objects.get_or_create(
        ticket=ticket,
        sender=demo_admin,
        message="Проверили доступ, материал снова доступен.",
    )

    Notification.objects.get_or_create(
        user=demo_admin,
        title="Новая заявка на курс",
        message=f'{demo_student} отправил заявку на курс "{courses[2].title if len(courses) > 2 else "курс"}".',
    )
    Notification.objects.get_or_create(
        user=demo_student,
        title="Заявка одобрена",
        message=f'Вы зачислены на курс "{courses[0].title if courses else "курс"}".',
    )


def rollback_learning_process(apps, schema_editor):
    Users = apps.get_model("main", "Users")
    Lesson = apps.get_model("main", "Lesson")
    StudyGroup = apps.get_model("main", "StudyGroup")
    TeacherAvailability = apps.get_model("main", "TeacherAvailability")

    Users.objects.filter(email__in=[DEMO_ADMIN_EMAIL, DEMO_STUDENT_EMAIL]).delete()
    StudyGroup.objects.filter(name__endswith=" - группа 1").delete()
    Lesson.objects.filter(title__contains=": занятие ").delete()
    TeacherAvailability.objects.filter(day_of_week__in=(1, 3, 5), start_time=time(18, 0), end_time=time(20, 30)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0008_rename_target_audience_for_whom_description"),
    ]

    operations = [
        migrations.RunPython(seed_learning_process, rollback_learning_process),
    ]
