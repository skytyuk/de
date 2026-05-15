from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from main.models import (
    Application,
    ApplicationStatusHistory,
    Course,
    CourseCategory,
    CourseModule,
    CourseTag,
    Enrollment,
    Lesson,
    Material,
    Notification,
    Roles,
    Schedule,
    Users,
)
from main.session_auth import SESSION_USER_ID_KEY


class RoleUserFlowTests(TestCase):
    def setUp(self):
        self.student_role, _ = Roles.objects.get_or_create(name="student")
        self.user = Users(
            last_name="Petrov",
            first_name="Petr",
            middle_name="Petrovich",
            email="student@example.com",
            phone="+79991112233",
            role=self.student_role,
        )
        self.user.set_password("Strongpass123!")
        self.user.save()
        self.category = CourseCategory.objects.create(name="Programming")
        self.course = Course.objects.create(
            category=self.category,
            title="Python Basic",
            description="Course description",
            duration_hours=24,
            price=5000,
        )

    def login_session(self, user=None):
        user = user or self.user
        session = self.client.session
        session[SESSION_USER_ID_KEY] = user.id
        session.save()

    def test_user_can_apply_to_course_without_duplicate_notifications(self):
        admin_role, _ = Roles.objects.get_or_create(name="admin")
        admin_user = Users(
            last_name="Adminov",
            first_name="Admin",
            middle_name="Adminovich",
            email="admin-notify@example.com",
            phone="+79991112236",
            role=admin_role,
        )
        admin_user.set_password("Strongpass123!")
        admin_user.save()
        self.login_session()

        response = self.client.post(reverse("role_user:apply_course", args=[self.course.id]))

        self.assertRedirects(
            response,
            f"{reverse('role_user:course_detail', args=[self.course.id])}?applied=1",
        )
        application = Application.objects.get(student=self.user, course=self.course)
        self.assertEqual(application.status, Application.ApplicationStatus.NEW)
        self.assertEqual(Notification.objects.filter(user=self.user, title="Заявка отправлена").count(), 1)
        self.assertEqual(Notification.objects.filter(user=admin_user, title="Новая заявка на курс").count(), 1)

        self.client.post(reverse("role_user:apply_course", args=[self.course.id]))

        self.assertEqual(Notification.objects.filter(user=self.user, title="Заявка отправлена").count(), 1)
        self.assertEqual(Notification.objects.filter(user=admin_user, title="Новая заявка на курс").count(), 1)

    def test_course_search_filters_by_title_tag_and_level(self):
        Course.objects.create(
            category=self.category,
            title="Design Advanced",
            description="Design course",
            level=Course.CourseLevel.ADVANCED,
            for_whom_description="Designers",
            duration_hours=16,
            price=3000,
        )
        design_course = Course.objects.get(title="Design Advanced")
        figma_tag, _ = CourseTag.objects.get_or_create(name="figma")
        design_tag, _ = CourseTag.objects.get_or_create(name="design")
        design_course.tags.add(figma_tag, design_tag)
        self.course.level = Course.CourseLevel.BEGINNER
        self.course.save(update_fields=["level"])
        python_tag, _ = CourseTag.objects.get_or_create(name="python")
        backend_tag, _ = CourseTag.objects.get_or_create(name="backend")
        self.course.tags.add(python_tag, backend_tag)
        self.login_session()

        response = self.client.get(reverse("role_user:courses"), {"q": "Python"})

        self.assertContains(response, "Python Basic")
        self.assertNotContains(response, "Design Advanced")

        response = self.client.get(reverse("role_user:courses"), {"q": "figma"})

        self.assertNotContains(response, "Design Advanced")

        response = self.client.get(reverse("role_user:courses"), {"tag": "figma"})

        self.assertContains(response, "Design Advanced")
        self.assertNotContains(response, "Python Basic")

        response = self.client.get(reverse("role_user:courses"), {"level": Course.CourseLevel.ADVANCED})

        self.assertContains(response, "Design Advanced")
        self.assertNotContains(response, "Python Basic")

        response = self.client.get(reverse("main:notification_counts"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread"], 0)

    def test_non_student_cannot_open_user_section(self):
        teacher_role, _ = Roles.objects.get_or_create(name="teacher")
        teacher = Users(
            last_name="Ivanov",
            first_name="Ivan",
            middle_name="Ivanovich",
            email="teacher@example.com",
            phone="+79991112234",
            role=teacher_role,
        )
        teacher.set_password("Strongpass123!")
        teacher.save()
        self.login_session(teacher)

        response = self.client.get(reverse("role_user:courses"))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Application.objects.filter(student=teacher).exists())

    def test_header_links_are_visible_only_for_student(self):
        self.login_session()

        response = self.client.get(reverse("main:index"))

        self.assertContains(response, reverse("role_user:courses"))
        self.assertContains(response, reverse("role_user:notifications"))

        teacher_role, _ = Roles.objects.get_or_create(name="teacher")
        teacher = Users(
            last_name="Ivanov",
            first_name="Ivan",
            middle_name="Ivanovich",
            email="teacher-links@example.com",
            phone="+79991112235",
            role=teacher_role,
        )
        teacher.set_password("Strongpass123!")
        teacher.save()
        self.login_session(teacher)

        response = self.client.get(reverse("main:index"))

        self.assertNotContains(response, reverse("role_user:courses"))
        self.assertNotContains(response, reverse("role_user:notifications"))

    def test_approved_application_creates_enrollment_notification_and_history(self):
        application = Application.objects.create(student=self.user, course=self.course)

        application.status = Application.ApplicationStatus.APPROVED
        application.save(update_fields=["status", "updated_at"])

        self.assertTrue(Enrollment.objects.filter(student=self.user, course=self.course).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                title="Заявка одобрена",
            ).exists()
        )
        self.assertTrue(
            ApplicationStatusHistory.objects.filter(
                application=application,
                old_status=Application.ApplicationStatus.NEW,
                new_status=Application.ApplicationStatus.APPROVED,
            ).exists()
        )

    def test_enrolled_user_can_open_course_materials(self):
        module = CourseModule.objects.create(course=self.course, title="Module 1", sort_order=1)
        lesson = Lesson.objects.create(module=module, title="Lesson 1", sort_order=1)
        Material.objects.create(
            lesson=lesson,
            title="Guide",
            material_type=Material.MaterialType.LINK,
            file_url="https://example.com/guide",
        )
        group = self.course.groups.create(name="Student group")
        Enrollment.objects.create(student=self.user, course=self.course, group=group)
        schedule = Schedule.objects.create(
            group=group,
            lesson=lesson,
            teacher=None,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
            is_visible_to_students=True,
        )
        self.login_session()

        response = self.client.get(reverse("role_user:my_course_detail", args=[self.course.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Basic")
        self.assertContains(response, "Открыть занятие")

        response = self.client.get(reverse("role_user:lesson_detail", args=[self.course.id, schedule.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lesson 1")
        self.assertContains(response, "Guide")
