from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from django.utils import timezone

from main.models import Application, Course, CourseCategory, CourseModule, Enrollment, Lesson, Roles, Schedule, StudyGroup, Users
from main.session_auth import SESSION_USER_ID_KEY


class RoleAdminTests(TestCase):
    def setUp(self):
        self.admin_role, _ = Roles.objects.get_or_create(name="admin")
        self.teacher_role, _ = Roles.objects.get_or_create(name="teacher")
        self.admin_user = self.create_user(
            role=self.admin_role,
            email="admin@example.com",
            phone="+79990001001",
        )
        self.teacher_user = self.create_user(
            role=self.teacher_role,
            email="teacher@example.com",
            phone="+79990001002",
        )

    def create_user(self, role, email, phone):
        user = Users(
            last_name="Ivanov",
            first_name="Ivan",
            middle_name="Ivanovich",
            email=email,
            phone=phone,
            role=role,
        )
        user.set_password("Strongpass123!")
        user.save()
        return user

    def login_session(self, user):
        session = self.client.session
        session[SESSION_USER_ID_KEY] = user.id
        session.save()

    def test_admin_can_open_dashboard(self):
        self.login_session(self.admin_user)

        response = self.client.get(reverse("role_admin:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Админка")

    def test_non_admin_cannot_open_dashboard(self):
        self.login_session(self.teacher_user)

        response = self.client.get(reverse("role_admin:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_course_from_table_form(self):
        self.login_session(self.admin_user)
        category = CourseCategory.objects.create(name="Test category")

        response = self.client.post(
            reverse("role_admin:record_create", args=["course"]),
            {
                "category": category.id,
                "title": "Admin created course",
                "description": "Created from role_admin.",
                "level": Course.CourseLevel.BEGINNER,
                "for_whom_description": "Students",
                "duration_hours": 12,
                "price": "5000.00",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("role_admin:table_detail", args=["course"]) + "?notice=Запись+добавлена.")
        self.assertTrue(Course.objects.filter(title="Admin created course").exists())

    def test_admin_can_export_table_json(self):
        self.login_session(self.admin_user)

        response = self.client.get(reverse("role_admin:export_table_json", args=["course"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertIn(b'"model": "main.course"', response.content)

    def test_table_detail_shows_all_course_columns(self):
        self.login_session(self.admin_user)

        response = self.client.get(reverse("role_admin:table_detail", args=["course"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "level")
        self.assertContains(response, "for_whom_description")
        self.assertNotIn("image", response.context["columns"])
        self.assertNotIn("tags", response.context["columns"])

    def test_admin_can_process_course_application(self):
        student_role, _ = Roles.objects.get_or_create(name="student")
        student = self.create_user(
            role=student_role,
            email="student-application@example.com",
            phone="+79990001003",
        )
        category = CourseCategory.objects.create(name="Applications category")
        course = Course.objects.create(
            category=category,
            title="Applications course",
            level=Course.CourseLevel.BEGINNER,
            for_whom_description="Students",
            duration_hours=10,
            price=1000,
        )
        group = StudyGroup.objects.create(course=course, teacher=self.teacher_user, name="Applications group")
        application = Application.objects.create(student=student, course=course)
        self.login_session(self.admin_user)

        response = self.client.post(
            reverse("role_admin:applications"),
            {
                "application_id": application.id,
                "status": Application.ApplicationStatus.APPROVED,
                "group": group.id,
                "comment": "Принято",
            },
        )

        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.ApplicationStatus.APPROVED)
        self.assertEqual(application.comment, "Принято")
        self.assertTrue(Enrollment.objects.filter(student=student, course=course).exists())
        self.assertEqual(Enrollment.objects.get(student=student, course=course).group, group)

    def test_admin_can_create_schedule_item(self):
        self.login_session(self.admin_user)
        category = CourseCategory.objects.create(name="Schedule category")
        course = Course.objects.create(
            category=category,
            title="Schedule course",
            level=Course.CourseLevel.BEGINNER,
            for_whom_description="Students",
            duration_hours=10,
            price=1000,
        )
        group = StudyGroup.objects.create(course=course, teacher=self.teacher_user, name="Schedule group")
        module = CourseModule.objects.create(course=course, title="Schedule module", sort_order=1)
        lesson = Lesson.objects.create(module=module, title="Schedule lesson", sort_order=1)

        start_at = timezone.now() + timedelta(days=1)
        end_at = start_at + timedelta(hours=1)
        response = self.client.post(
            reverse("role_admin:schedule"),
            {
                "group": group.id,
                "lesson": lesson.id,
                "teacher": self.teacher_user.id,
                "start_at": timezone.localtime(start_at).strftime("%Y-%m-%dT%H:%M"),
                "end_at": timezone.localtime(end_at).strftime("%Y-%m-%dT%H:%M"),
                "meeting_code": "AE-TEST",
            },
        )

        self.assertEqual(response.status_code, 200)
        schedule = Schedule.objects.get(group=group, lesson=lesson)
        self.assertEqual(schedule.teacher, self.teacher_user)
        self.assertEqual(schedule.meeting_code, "AE-TEST")
