from functools import wraps
from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from main.models import (
    Application,
    Course,
    CourseCategory,
    CourseTag,
    Enrollment,
    LessonProgress,
    Notification,
    Schedule,
    StudentSubmission,
    StudentTestAnswer,
    Test,
    TestAnswer,
    TestAttempt,
    Users,
)
from main.services import refresh_lesson_progress
from main.session_auth import get_current_user, login_required
from role_admin.permissions import is_admin_user


STUDENT_ROLE_NAME = "student"


def student_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        role_name = getattr(getattr(request.current_user, "role", None), "name", "")
        if role_name.strip().lower() != STUDENT_ROLE_NAME:
            return HttpResponseForbidden("Раздел доступен только студентам.")
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)


def _course_queryset():
    return (
        Course.objects
        .select_related("category")
        .prefetch_related("tags", "modules__lessons__materials", "course_teachers__teacher")
    )


def _course_learning_queryset():
    return (
        Course.objects
        .select_related("category")
        .prefetch_related(
            "course_teachers__teacher",
            "tags",
            "modules__lessons__materials",
            "modules__lessons__assignments",
            "modules__lessons__tests",
        )
    )


def _visible_schedule_queryset(user, course=None):
    schedules = (
        Schedule.objects
        .filter(
            group__enrollments__student=user,
            is_visible_to_students=True,
        )
        .exclude(status=Schedule.ScheduleStatus.CANCELLED)
        .select_related("group", "group__course", "lesson", "teacher")
        .distinct()
    )
    if course:
        schedules = schedules.filter(group__course=course)
    return schedules


def _next_schedule_for_user(user, course=None):
    schedules = (
        _visible_schedule_queryset(user, course)
        .filter(start_at__gte=timezone.now())
        .order_by("start_at")
    )
    return schedules.first()


def _course_tags(course):
    return [tag.name for tag in course.tags.all()]


def _course_filter_url(**params):
    query = {}
    for key, value in params.items():
        if isinstance(value, (list, tuple, set)):
            values = [item for item in value if item]
            if values:
                query[key] = values
        elif value:
            query[key] = value
    return f"?{urlencode(query, doseq=True)}" if query else "?"


def _schedule_duration_minutes(schedule):
    if not schedule:
        return None
    return round((schedule.end_at - schedule.start_at).total_seconds() / 60)


def _application_label(application):
    if not application:
        return ""
    labels = {
        Application.ApplicationStatus.NEW: "Заявка отправлена",
        Application.ApplicationStatus.APPROVED: "Заявка одобрена",
        Application.ApplicationStatus.REJECTED: "Заявка отклонена",
        Application.ApplicationStatus.CANCELLED: "Заявка отменена",
    }
    return labels.get(application.status, application.get_status_display())


def _notify_admins_about_application(application):
    admins = [
        user
        for user in Users.objects.select_related("role").all()
        if is_admin_user(user)
    ]
    Notification.objects.bulk_create(
        [
            Notification(
                user=admin,
                title="Новая заявка на курс",
                message=(
                    f'{application.student} отправил заявку на курс '
                    f'"{application.course.title}".'
                ),
            )
            for admin in admins
        ]
    )


@student_required
def dashboard(request):
    user = request.current_user
    enrollments = (
        Enrollment.objects
        .filter(student=user)
        .select_related("course", "group")
        .order_by("-enrolled_at")[:3]
    )
    applications = (
        Application.objects
        .filter(student=user)
        .select_related("course")
        .order_by("-updated_at")[:3]
    )

    return render(
        request,
        "role_user/dashboard.html",
        {
            "enrollments": enrollments,
            "applications": applications,
            "next_schedule": _next_schedule_for_user(user),
            "unread_notifications_count": Notification.objects.filter(user=user, is_read=False).count(),
        },
    )


def course_list(request):
    user = get_current_user(request)
    user_is_student = bool(user and user.role and user.role.name.strip().lower() == STUDENT_ROLE_NAME)
    if user and not user_is_student:
        return HttpResponseForbidden("Раздел доступен только студентам и гостям.")
    base_courses = _course_queryset().filter(is_active=True)
    courses = base_courses.order_by("title")
    search_query = request.GET.get("q", "").strip()
    selected_level = request.GET.get("level", "").strip()
    selected_category = request.GET.get("category", "").strip()
    selected_tags = [
        tag.strip()
        for tag in request.GET.getlist("tag")
        if tag.strip()
    ]

    if search_query:
        courses = courses.filter(title__icontains=search_query)
    if selected_level:
        courses = courses.filter(level=selected_level)
    if selected_category:
        courses = courses.filter(category_id=selected_category)
    for selected_tag in selected_tags:
        courses = courses.filter(tags__name__iexact=selected_tag)

    all_tags = sorted(
        CourseTag.objects.filter(courses__is_active=True).values_list("name", flat=True).distinct(),
        key=str.casefold,
    )
    tag_items = [
        {
            "name": tag,
            "is_selected": tag in selected_tags,
            "url": _course_filter_url(
                q=search_query,
                level=selected_level,
                category=selected_category,
                tag=(
                    [selected for selected in selected_tags if selected != tag]
                    if tag in selected_tags
                    else [*selected_tags, tag]
                ),
            ),
        }
        for tag in all_tags
    ]
    category_items = [
        {
            "id": category.id,
            "name": category.name,
            "is_selected": str(category.id) == selected_category,
        }
        for category in CourseCategory.objects.filter(courses__is_active=True).distinct().order_by("name")
    ]

    applications = {}
    enrollments = {}
    if user_is_student:
        applications = {
            application.course_id: application
            for application in Application.objects.filter(student=user)
        }
        enrollments = {
            enrollment.course_id: enrollment
            for enrollment in Enrollment.objects.filter(student=user)
        }

    course_items = []
    for course in courses:
        application = applications.get(course.id)
        enrollment = enrollments.get(course.id)
        course_items.append(
            {
                "course": course,
                "application": application,
                "application_label": _application_label(application),
                "enrollment": enrollment,
                "tags": [
                    {
                        "name": tag,
                        "is_selected": tag in selected_tags,
                        "url": _course_filter_url(
                            q=search_query,
                            level=selected_level,
                            category=selected_category,
                            tag=(
                                [selected for selected in selected_tags if selected != tag]
                                if tag in selected_tags
                                else [*selected_tags, tag]
                            ),
                        ),
                    }
                    for tag in _course_tags(course)
                ],
                "can_apply": not enrollment and (
                    not user
                    or (
                        user_is_student
                        and (
                            not application
                            or application.status in {
                                Application.ApplicationStatus.REJECTED,
                                Application.ApplicationStatus.CANCELLED,
                            }
                        )
                    )
                ),
            }
        )

    return render(
        request,
        "role_user/course_list.html",
        {
            "course_items": course_items,
            "search_query": search_query,
            "selected_level": selected_level,
            "selected_category": selected_category,
            "selected_tags": selected_tags,
            "course_levels": Course.CourseLevel.choices,
            "course_categories": category_items,
            "tag_items": tag_items,
            "user_is_student": user_is_student,
        },
    )


def course_detail(request, course_id):
    user = get_current_user(request)
    user_is_student = bool(user and user.role and user.role.name.strip().lower() == STUDENT_ROLE_NAME)
    if user and not user_is_student:
        return HttpResponseForbidden("Раздел доступен только студентам и гостям.")
    course = get_object_or_404(_course_queryset(), pk=course_id, is_active=True)
    application = Application.objects.filter(student=user, course=course).first() if user_is_student else None
    enrollment = Enrollment.objects.filter(student=user, course=course).first() if user_is_student else None

    return render(
        request,
        "role_user/course_detail.html",
        {
            "course": course,
            "application": application,
            "application_label": _application_label(application),
            "enrollment": enrollment,
            "can_apply": not enrollment and (
                not user
                or (
                    user_is_student
                    and (
                        not application
                        or application.status in {
                            Application.ApplicationStatus.REJECTED,
                            Application.ApplicationStatus.CANCELLED,
                        }
                    )
                )
            ),
            "application_sent": request.GET.get("applied") == "1",
            "course_tags": _course_tags(course),
            "user_is_student": user_is_student,
        },
    )


@student_required
def apply_course(request, course_id):
    if request.method != "POST":
        return redirect("role_user:course_detail", course_id=course_id)

    user = request.current_user
    course = get_object_or_404(Course, pk=course_id, is_active=True)

    if Enrollment.objects.filter(student=user, course=course).exists():
        return redirect("role_user:my_course_detail", course_id=course.id)

    application, created = Application.objects.get_or_create(
        student=user,
        course=course,
        defaults={"status": Application.ApplicationStatus.NEW},
    )
    should_notify = created

    if application.status == Application.ApplicationStatus.APPROVED:
        Enrollment.objects.get_or_create(
            student=user,
            course=course,
            defaults={
                "application": application,
                "status": Enrollment.EnrollmentStatus.ACTIVE,
            },
        )
        return redirect("role_user:my_course_detail", course_id=course.id)

    if not created and application.status in {
        Application.ApplicationStatus.REJECTED,
        Application.ApplicationStatus.CANCELLED,
    }:
        application.status = Application.ApplicationStatus.NEW
        application.comment = ""
        application.save(update_fields=["status", "comment", "updated_at"])
        should_notify = True

    if should_notify:
        Notification.objects.create(
            user=user,
            title="Заявка отправлена",
            message=f'Заявка на курс "{course.title}" отправлена на рассмотрение.',
        )
        _notify_admins_about_application(application)

    return redirect(f"{reverse('role_user:course_detail', kwargs={'course_id': course.id})}?applied=1")


@student_required
def my_courses(request):
    enrollments = (
        Enrollment.objects
        .filter(student=request.current_user)
        .select_related("course", "course__category", "group")
        .order_by("-enrolled_at")
    )
    for enrollment in enrollments:
        schedule = None
        if enrollment.group:
            schedule = (
                Schedule.objects
                .filter(group=enrollment.group, is_visible_to_students=True)
                .exclude(status=Schedule.ScheduleStatus.CANCELLED)
                .order_by("start_at")
                .first()
            )
        enrollment.lesson_duration_minutes = _schedule_duration_minutes(schedule)
        enrollment.course_tags = _course_tags(enrollment.course)
    return render(request, "role_user/my_courses.html", {"enrollments": enrollments})


@student_required
def my_course_detail(request, course_id):
    user = request.current_user
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course", "group", "group__teacher", "application"),
        student=user,
        course_id=course_id,
    )
    course = get_object_or_404(_course_learning_queryset(), pk=course_id)
    visible_schedules = _visible_schedule_queryset(user, course)
    schedules = (
        visible_schedules
        .filter(start_at__gte=timezone.now())
        .order_by("start_at")
        [:8]
    )
    archived_schedules = (
        visible_schedules
        .filter(end_at__lt=timezone.now())
        .order_by("-start_at")
        [:10]
    )
    for schedule in list(schedules) + list(archived_schedules):
        schedule.duration_minutes = _schedule_duration_minutes(schedule)
    progress_by_lesson = {
        progress.lesson_id: progress
        for progress in LessonProgress.objects.filter(student=user, lesson__module__course=course)
    }
    submissions_by_assignment = {
        submission.assignment_id: submission
        for submission in (
            StudentSubmission.objects
            .filter(student=user, assignment__lesson__module__course=course)
            .select_related("assignment")
        )
    }
    attempts_by_test = {}
    test_attempts = (
        TestAttempt.objects
        .filter(student=user, test__lesson__module__course=course)
        .select_related("test")
        .order_by("test_id", "-finished_at", "-started_at")
    )
    for attempt in test_attempts:
        attempts_by_test.setdefault(attempt.test_id, attempt)

    lessons_count = 0
    completed_lessons_count = 0
    for module in course.modules.all():
        for lesson in module.lessons.all():
            lessons_count += 1
            lesson.user_progress = progress_by_lesson.get(lesson.id)
            if lesson.user_progress and lesson.user_progress.status == LessonProgress.ProgressStatus.COMPLETED:
                completed_lessons_count += 1
            for assignment in lesson.assignments.all():
                assignment.user_submission = submissions_by_assignment.get(assignment.id)
            for test in lesson.tests.all():
                test.user_attempt = attempts_by_test.get(test.id)

    progress_percent = round((completed_lessons_count / lessons_count) * 100) if lessons_count else 0

    return render(
        request,
        "role_user/my_course_detail.html",
        {
            "course": course,
            "enrollment": enrollment,
            "next_schedule": _next_schedule_for_user(user, course),
            "schedules": schedules,
            "archived_schedules": archived_schedules,
            "progress_by_lesson": progress_by_lesson,
            "course_tags": _course_tags(course),
            "lessons_count": lessons_count,
            "completed_lessons_count": completed_lessons_count,
            "progress_percent": progress_percent,
        },
    )


@student_required
def lesson_detail(request, course_id, schedule_id):
    user = request.current_user
    enrollment = get_object_or_404(
        Enrollment.objects.select_related("course", "group", "group__teacher"),
        student=user,
        course_id=course_id,
    )
    course = get_object_or_404(Course.objects.select_related("category"), pk=course_id)
    schedule = get_object_or_404(
        _visible_schedule_queryset(user, course),
        pk=schedule_id,
    )
    lesson = schedule.lesson
    assignments = []
    tests = []
    progress = None
    attendance = None
    submission_errors = {}

    if lesson:
        if request.method == "POST" and request.POST.get("action") == "submit_assignment":
            assignment = get_object_or_404(lesson.assignments.all(), pk=request.POST.get("assignment"))
            answer_text = request.POST.get("answer_text", "").strip()
            file_url = request.POST.get("file_url", "").strip()
            uploaded_file = request.FILES.get("file")
            existing_submission = StudentSubmission.objects.filter(assignment=assignment, student=user).first()
            has_file = bool(uploaded_file or (existing_submission and existing_submission.file))
            has_url = bool(file_url)
            if has_file and has_url:
                submission_errors[assignment.id] = "Заполните только одно поле: файл или ссылку."
            elif not has_file and not has_url:
                submission_errors[assignment.id] = "Добавьте файл или ссылку к ответу."
            else:
                submission, _ = StudentSubmission.objects.get_or_create(
                    assignment=assignment,
                    student=user,
                )
                submission.answer_text = answer_text
                submission.file_url = file_url
                if uploaded_file:
                    submission.file = uploaded_file
                submission.status = StudentSubmission.SubmissionStatus.SUBMITTED
                submission.score = None
                submission.feedback = ""
                submission.checked_at = None
                submission.full_clean()
                submission.save()
                refresh_lesson_progress(user, lesson, schedule)
                teacher = schedule.teacher or schedule.group.teacher
                if teacher:
                    Notification.objects.create(
                        user=teacher,
                        title="Новый ответ на задание",
                        message=f'{user} отправил ответ на задание "{assignment.title}".',
                    )
                return redirect("role_user:lesson_detail", course_id=course.id, schedule_id=schedule.id)

        assignments = list(lesson.assignments.all())
        submissions_by_assignment = {
            submission.assignment_id: submission
            for submission in StudentSubmission.objects.filter(student=user, assignment__lesson=lesson)
        }
        for assignment in assignments:
            assignment.user_submission = submissions_by_assignment.get(assignment.id)
            assignment.submission_error = submission_errors.get(assignment.id)

        tests = list(lesson.tests.all())
        attempts_by_test = {}
        for attempt in (
            TestAttempt.objects
            .filter(student=user, test__lesson=lesson)
            .order_by("test_id", "-finished_at", "-started_at")
        ):
            attempts_by_test.setdefault(attempt.test_id, attempt)
        for test in tests:
            test.user_attempt = attempts_by_test.get(test.id)

        progress = refresh_lesson_progress(user, lesson, schedule)

    attendance = schedule.attendance.filter(student=user).first()

    return render(
        request,
        "role_user/lesson_detail.html",
        {
            "course": course,
            "enrollment": enrollment,
            "schedule": schedule,
            "lesson": lesson,
            "assignments": assignments,
            "tests": tests,
            "progress": progress,
            "attendance": attendance,
            "duration_minutes": _schedule_duration_minutes(schedule),
            "is_archive": schedule.end_at < timezone.now(),
            "submission_errors": submission_errors,
        },
    )


@student_required
def test_detail(request, course_id, schedule_id, test_id):
    user = request.current_user
    course = get_object_or_404(Course.objects.select_related("category"), pk=course_id)
    schedule = get_object_or_404(_visible_schedule_queryset(user, course), pk=schedule_id)
    test = get_object_or_404(
        Test.objects.prefetch_related("questions__answers"),
        pk=test_id,
        lesson=schedule.lesson,
    )
    latest_attempt = (
        TestAttempt.objects
        .filter(student=user, test=test)
        .order_by("-finished_at", "-started_at")
        .first()
    )

    if request.method == "POST":
        total_score = sum(question.score for question in test.questions.all())
        score = 0
        selected_answers = {}

        for question in test.questions.all():
            answer_id = request.POST.get(f"question_{question.id}")
            answer = question.answers.filter(pk=answer_id).first() if answer_id else None
            if answer and answer.is_correct:
                score += question.score
            selected_answers[question.id] = answer

        percent = round((score / total_score) * 100) if total_score else 0
        attempt = TestAttempt.objects.create(
            test=test,
            student=user,
            score=percent,
            status=(
                TestAttempt.AttemptStatus.PASSED
                if percent >= test.passing_score
                else TestAttempt.AttemptStatus.FAILED
            ),
            finished_at=timezone.now(),
        )
        for question_id, answer in selected_answers.items():
            StudentTestAnswer.objects.create(
                attempt=attempt,
                question_id=question_id,
                answer=answer,
            )
        refresh_lesson_progress(user, test.lesson, schedule)
        Notification.objects.create(
            user=user,
            title="Результат теста",
            message=f'Тест "{test.title}" завершен на {percent}%.',
        )
        return redirect("role_user:test_detail", course_id=course.id, schedule_id=schedule.id, test_id=test.id)

    return render(
        request,
        "role_user/test_detail.html",
        {
            "course": course,
            "schedule": schedule,
            "test": test,
            "latest_attempt": latest_attempt,
        },
    )


@student_required
def notifications(request):
    user = request.current_user
    if request.method == "POST" and request.POST.get("action") == "mark_read":
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        return redirect("role_user:notifications")

    now = timezone.now()
    soon = now + timedelta(days=7)
    stored_notifications = Notification.objects.filter(user=user).order_by("-created_at")[:30]
    application_updates = (
        Application.objects
        .filter(student=user)
        .exclude(status=Application.ApplicationStatus.NEW)
        .select_related("course")
        .order_by("-updated_at")[:20]
    )
    upcoming_schedules = (
        Schedule.objects
        .filter(
            group__enrollments__student=user,
            is_visible_to_students=True,
            start_at__gte=now,
            start_at__lte=soon,
        )
        .exclude(status=Schedule.ScheduleStatus.CANCELLED)
        .select_related("group", "group__course", "lesson", "teacher")
        .order_by("start_at")
        .distinct()[:20]
    )
    submission_results = (
        StudentSubmission.objects
        .filter(student=user)
        .filter(Q(score__isnull=False) | Q(status=StudentSubmission.SubmissionStatus.CHECKED))
        .select_related("assignment", "assignment__lesson", "assignment__lesson__module", "assignment__lesson__module__course")
        .order_by("-checked_at", "-submitted_at")[:20]
    )
    test_results = (
        TestAttempt.objects
        .filter(student=user)
        .exclude(status=TestAttempt.AttemptStatus.STARTED)
        .select_related("test", "test__lesson", "test__lesson__module", "test__lesson__module__course")
        .order_by("-finished_at", "-started_at")[:20]
    )

    return render(
        request,
        "role_user/notifications.html",
        {
            "stored_notifications": stored_notifications,
            "application_updates": application_updates,
            "upcoming_schedules": upcoming_schedules,
            "submission_results": submission_results,
            "test_results": test_results,
        },
    )
