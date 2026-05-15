from itertools import cycle

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


STUDENTS = [
    ("student.anna@example.com", "+79993000101", "Иванова", "Анна", "Сергеевна"),
    ("student.igor@example.com", "+79993000102", "Соколов", "Игорь", "Павлович"),
    ("student.maria@example.com", "+79993000103", "Морозова", "Мария", "Ильинична"),
    ("student.nikita@example.com", "+79993000104", "Лебедев", "Никита", "Алексеевич"),
    ("student.daria@example.com", "+79993000105", "Козлова", "Дарья", "Олеговна"),
    ("student.roman@example.com", "+79993000106", "Новиков", "Роман", "Дмитриевич"),
    ("student.alina@example.com", "+79993000107", "Павлова", "Алина", "Викторовна"),
    ("student.timur@example.com", "+79993000108", "Федоров", "Тимур", "Русланович"),
    ("student.ksenia@example.com", "+79993000109", "Васильева", "Ксения", "Андреевна"),
    ("student.oleg@example.com", "+79993000110", "Михайлов", "Олег", "Игоревич"),
    ("student.sofia@example.com", "+79993000111", "Алексеева", "София", "Максимовна"),
    ("student.artem@example.com", "+79993000112", "Громов", "Артем", "Станиславович"),
]


def seed_more_students(apps, schema_editor):
    Roles = apps.get_model("main", "Roles")
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    StudyGroup = apps.get_model("main", "StudyGroup")
    Application = apps.get_model("main", "Application")
    ApplicationStatusHistory = apps.get_model("main", "ApplicationStatusHistory")
    Enrollment = apps.get_model("main", "Enrollment")
    Schedule = apps.get_model("main", "Schedule")
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
    admin_user = Users.objects.filter(role__name="admin").order_by("id").first()
    courses = list(Course.objects.filter(is_active=True).order_by("id"))
    groups = list(StudyGroup.objects.select_related("course", "teacher").filter(is_active=True).order_by("id"))
    if not courses or not groups:
        return

    group_cycle = cycle(groups)
    status_cycle = cycle(["approved", "approved", "approved", "new", "rejected"])
    created_students = []

    for index, (email, phone, last_name, first_name, middle_name) in enumerate(STUDENTS, start=1):
        user, _ = Users.objects.get_or_create(
            email=email,
            defaults={
                "last_name": last_name,
                "first_name": first_name,
                "middle_name": middle_name,
                "phone": phone,
                "password": make_password("Student123!"),
                "role": student_role,
            },
        )
        created_students.append(user)

        group = next(group_cycle)
        status = next(status_cycle)
        application, _ = Application.objects.get_or_create(
            student=user,
            course=group.course,
            defaults={
                "status": status,
                "comment": "Демонстрационная заявка студента.",
            },
        )
        ApplicationStatusHistory.objects.get_or_create(
            application=application,
            old_status="new",
            new_status=status,
            defaults={
                "changed_by": admin_user,
                "comment": "История обработки заявки для демонстрации.",
            },
        )

        if status == "approved":
            Enrollment.objects.get_or_create(
                student=user,
                course=group.course,
                defaults={
                    "group": group,
                    "application": application,
                    "status": "active",
                },
            )
            Payment.objects.get_or_create(
                student=user,
                course=group.course,
                defaults={
                    "amount": group.course.price or 0,
                    "status": "paid" if index % 4 else "pending",
                    "payment_method": "Банковская карта",
                    "paid_at": timezone.now() if index % 4 else None,
                },
            )
            Notification.objects.get_or_create(
                user=user,
                title="Заявка одобрена",
                message=f'Вы зачислены на курс "{group.course.title}".',
            )
            if group.teacher:
                Notification.objects.get_or_create(
                    user=group.teacher,
                    title="Новый студент в группе",
                    message=f'{user} зачислен в группу "{group.name}".',
                )

            schedules = list(Schedule.objects.filter(group=group).select_related("lesson").order_by("start_at")[:3])
            for schedule_index, schedule in enumerate(schedules):
                LessonAttendance.objects.get_or_create(
                    schedule=schedule,
                    student=user,
                    defaults={
                        "status": "present" if schedule_index < 2 else "late",
                        "joined_at": schedule.start_at,
                        "left_at": schedule.end_at,
                    },
                )
                if schedule.lesson:
                    LessonProgress.objects.get_or_create(
                        student=user,
                        lesson=schedule.lesson,
                        defaults={
                            "status": "completed" if schedule_index < 2 else "in_progress",
                            "started_at": timezone.now(),
                            "completed_at": timezone.now() if schedule_index < 2 else None,
                        },
                    )

            assignment = Assignment.objects.filter(lesson__module__course=group.course).order_by("id").first()
            if assignment:
                submission, _ = StudentSubmission.objects.get_or_create(
                    assignment=assignment,
                    student=user,
                    defaults={
                        "answer_text": "Практическое задание выполнено в мобильном приложении.",
                        "status": "checked" if index % 2 else "submitted",
                        "score": 76 + (index % 20) if index % 2 else None,
                        "feedback": "Работа принята, есть небольшие замечания." if index % 2 else "",
                        "checked_at": timezone.now() if index % 2 else None,
                    },
                )
                if submission.status == "submitted" and group.teacher:
                    Notification.objects.get_or_create(
                        user=group.teacher,
                        title="Новое задание на проверку",
                        message=f'{user} отправил задание "{assignment.title}".',
                    )

            test = Test.objects.filter(lesson__module__course=group.course).order_by("id").first()
            if test:
                attempt, _ = TestAttempt.objects.get_or_create(
                    test=test,
                    student=user,
                    defaults={
                        "score": 70 + (index % 25),
                        "status": "passed",
                        "finished_at": timezone.now(),
                    },
                )
                for question in TestQuestion.objects.filter(test=test):
                    answer = TestAnswer.objects.filter(question=question, is_correct=True).first()
                    if answer:
                        StudentTestAnswer.objects.get_or_create(
                            attempt=attempt,
                            question=question,
                            defaults={"answer": answer},
                        )

            first_lesson = group.course.modules.order_by("sort_order").first()
            lesson = first_lesson.lessons.order_by("sort_order").first() if first_lesson else None
            if lesson and index <= 6:
                LessonComment.objects.get_or_create(
                    lesson=lesson,
                    user=user,
                    defaults={"text": "Нужен пример решения практического задания."},
                )

            if index <= 3:
                Certificate.objects.get_or_create(
                    student=user,
                    course=group.course,
                    defaults={"certificate_number": f"DEMO-2026-{index + 1:04d}"},
                )
            CourseReview.objects.get_or_create(
                student=user,
                course=group.course,
                defaults={
                    "rating": 4 + (index % 2),
                    "comment": "Удобно, что расписание и прогресс видны в личном кабинете.",
                },
            )

        if index in (2, 5, 8, 11):
            ticket, _ = SupportTicket.objects.get_or_create(
                user=user,
                subject="Вопрос по доступу к занятию",
                defaults={"status": "open" if index % 2 else "in_progress"},
            )
            SupportMessage.objects.get_or_create(
                ticket=ticket,
                sender=user,
                message="Не вижу ссылку на онлайн-занятие в мобильном приложении.",
            )
            if admin_user:
                SupportMessage.objects.get_or_create(
                    ticket=ticket,
                    sender=admin_user,
                    message="Проверяем расписание и доступ к группе.",
                )


def rollback_more_students(apps, schema_editor):
    Users = apps.get_model("main", "Users")
    Notification = apps.get_model("main", "Notification")

    emails = [student[0] for student in STUDENTS]
    Users.objects.filter(email__in=emails).delete()
    Notification.objects.filter(
        title__in=[
            "Новый студент в группе",
            "Новое задание на проверку",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0009_seed_learning_process_demo"),
    ]

    operations = [
        migrations.RunPython(seed_more_students, rollback_more_students),
    ]
