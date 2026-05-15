from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from main.models import (
    Assignment,
    Course,
    CourseModule,
    Enrollment,
    Lesson,
    LessonAttendance,
    Notification,
    Roles,
    Schedule,
    StudentSubmission,
    StudyGroup,
    Users,
)
from main.session_auth import SESSION_USER_ID_KEY


class RoleTeacherTests(TestCase):
    def setUp(self):
        self.teacher_role, _ = Roles.objects.get_or_create(name="teacher")
        self.student_role, _ = Roles.objects.get_or_create(name="student")
        self.teacher = self.create_user(self.teacher_role, "teacher-flow@example.com", "+79994000001")
        self.student = self.create_user(self.student_role, "student-flow@example.com", "+79994000002")
        self.course = Course.objects.create(title="Teacher course", duration_hours=12, price=1000)
        self.group = StudyGroup.objects.create(course=self.course, teacher=self.teacher, name="Teacher group")
        self.module = CourseModule.objects.create(course=self.course, title="Teacher module", sort_order=1)
        self.lesson = Lesson.objects.create(module=self.module, title="Teacher lesson", sort_order=1)
        self.assignment = Assignment.objects.create(lesson=self.lesson, title="Teacher assignment", max_score=100)
        Enrollment.objects.create(student=self.student, course=self.course, group=self.group)

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

    def test_teacher_can_open_dashboard(self):
        self.login_session(self.teacher)

        response = self.client.get(reverse("role_teacher:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Кабинет преподавателя")

    def test_teacher_can_grade_submission(self):
        submission = StudentSubmission.objects.create(
            assignment=self.assignment,
            student=self.student,
            answer_text="Answer",
        )
        self.login_session(self.teacher)

        response = self.client.post(
            reverse("role_teacher:submissions"),
            {
                "action": "grade_submission",
                "submission_id": submission.id,
                "score": "88",
                "feedback": "Good",
            },
        )

        self.assertRedirects(response, reverse("role_teacher:submissions"))
        submission.refresh_from_db()
        self.assertEqual(submission.score, 88)
        self.assertEqual(submission.status, StudentSubmission.SubmissionStatus.CHECKED)
        self.assertTrue(Notification.objects.filter(user=self.student, title="Задание проверено").exists())

    def test_teacher_can_mark_attendance(self):
        schedule = Schedule.objects.create(
            group=self.group,
            lesson=self.lesson,
            teacher=self.teacher,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
        )
        self.login_session(self.teacher)

        response = self.client.post(
            reverse("role_teacher:group_detail", args=[self.group.id]),
            {
                "action": "save_attendance",
                "schedule": schedule.id,
                f"student_{self.student.id}": LessonAttendance.AttendanceStatus.PRESENT,
            },
        )

        self.assertRedirects(response, reverse("role_teacher:group_detail", args=[self.group.id]))
        self.assertEqual(
            LessonAttendance.objects.get(schedule=schedule, student=self.student).status,
            LessonAttendance.AttendanceStatus.PRESENT,
        )
