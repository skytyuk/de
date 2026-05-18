from datetime import timedelta
from urllib.parse import urlencode

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from main.models import (
    Assignment,
    Course,
    CourseModule,
    Enrollment,
    Lesson,
    LessonAttendance,
    LessonComment,
    Material,
    Notification,
    Schedule,
    StudentSubmission,
    StudyGroup,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
)

from .permissions import teacher_required


def teacher_courses(user):
    return (
        Course.objects
        .filter(Q(course_teachers__teacher=user) | Q(groups__teacher=user))
        .select_related("category")
        .distinct()
    )


def teacher_groups(user):
    return (
        StudyGroup.objects
        .filter(Q(teacher=user) | Q(course__course_teachers__teacher=user))
        .select_related("course", "teacher")
        .distinct()
    )


def teacher_lessons(user):
    return (
        Lesson.objects
        .filter(module__course__in=teacher_courses(user))
        .select_related("module", "module__course")
        .order_by("module__course__title", "module__sort_order", "sort_order")
        .distinct()
    )


def teacher_submissions(user):
    return (
        StudentSubmission.objects
        .filter(assignment__lesson__module__course__in=teacher_courses(user))
        .select_related("student", "assignment", "assignment__lesson", "assignment__lesson__module", "assignment__lesson__module__course")
        .order_by("-submitted_at")
        .distinct()
    )


def notify_group(group, title, message):
    notifications = [
        Notification(user=enrollment.student, title=title, message=message)
        for enrollment in group.enrollments.select_related("student").filter(status="active")
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def user_display(user):
    parts = [user.last_name, user.first_name, user.middle_name]
    full_name = " ".join(part for part in parts if part)
    return full_name or user.email or f"Пользователь #{user.pk}"


def content_redirect(request, **overrides):
    query = {
        "mode": request.POST.get("mode") or request.GET.get("mode") or "materials",
        "course": request.POST.get("course") or request.GET.get("course") or "",
        "module": request.POST.get("module") or request.GET.get("module") or "",
        "lesson": request.POST.get("lesson") or request.GET.get("lesson") or "",
    }
    query.update(overrides)
    cleaned_query = {key: value for key, value in query.items() if value}
    url = reverse("role_teacher:content")
    if cleaned_query:
        url = f"{url}?{urlencode(cleaned_query)}"
    return redirect(f"{url}#teacher-content-workspace")


def submissions_redirect(request, **overrides):
    query = {
        "mode": request.POST.get("mode") or request.GET.get("mode") or "",
        "course": request.POST.get("course") or request.GET.get("course") or "",
        "group": request.POST.get("group") or request.GET.get("group") or "",
        "student": request.POST.get("student") or request.GET.get("student") or "",
    }
    query.update(overrides)
    cleaned_query = {key: value for key, value in query.items() if value}
    url = reverse("role_teacher:submissions")
    if cleaned_query:
        url = f"{url}?{urlencode(cleaned_query)}"
    return redirect(url)


def teacher_materials(user):
    return Material.objects.filter(lesson__module__course__in=teacher_courses(user))


def teacher_assignments(user):
    return Assignment.objects.filter(lesson__module__course__in=teacher_courses(user))


def teacher_tests(user):
    return Test.objects.filter(lesson__module__course__in=teacher_courses(user))


def filter_lesson_content(queryset, selected_course=None, selected_module=None, selected_lesson=None):
    if selected_lesson:
        return queryset.filter(lesson=selected_lesson)
    if selected_module:
        return queryset.filter(lesson__module=selected_module)
    if selected_course:
        return queryset.filter(lesson__module__course=selected_course)
    return queryset


def get_material_type(value):
    valid_types = {choice[0] for choice in Material.MaterialType.choices}
    return value if value in valid_types else Material.MaterialType.FILE


def resource_error(file_value, url_value, empty_message):
    has_file = bool(file_value)
    has_url = bool((url_value or "").strip())
    if has_file and has_url:
        return "Заполните только одно поле: файл или ссылку."
    if not has_file and not has_url:
        return empty_message
    return ""


@teacher_required
def dashboard(request):
    user = request.current_user
    now = timezone.now()
    groups = teacher_groups(user).annotate(students_count=Count("enrollments", filter=Q(enrollments__status="active")))
    upcoming_schedules = (
        Schedule.objects
        .filter(Q(teacher=user) | Q(group__in=teacher_groups(user)), start_at__gte=now)
        .select_related("group", "group__course", "lesson")
        .order_by("start_at")
        .distinct()[:5]
    )
    unchecked_submissions = teacher_submissions(user).filter(status=StudentSubmission.SubmissionStatus.SUBMITTED).count()
    recent_attempts = (
        TestAttempt.objects
        .filter(test__lesson__module__course__in=teacher_courses(user))
        .exclude(status=TestAttempt.AttemptStatus.STARTED)
        .select_related("student", "test", "test__lesson", "test__lesson__module", "test__lesson__module__course")
        .order_by("-finished_at", "-started_at")[:5]
    )

    return render(
        request,
        "role_teacher/dashboard.html",
        {
            "groups": groups[:5],
            "courses_count": teacher_courses(user).count(),
            "groups_count": groups.count(),
            "unchecked_submissions_count": unchecked_submissions,
            "upcoming_schedules": upcoming_schedules,
            "recent_attempts": recent_attempts,
            "unread_notifications_count": Notification.objects.filter(user=user, is_read=False).count(),
        },
    )


@teacher_required
def groups(request):
    courses = teacher_courses(request.current_user).order_by("title")
    selected_course_id = request.GET.get("course", "").strip()
    selected_course = courses.filter(pk=selected_course_id).first() if selected_course_id.isdigit() else None
    groups_list = (
        teacher_groups(request.current_user)
        .annotate(students_count=Count("enrollments", filter=Q(enrollments__status="active")))
        .order_by("course__title", "name")
    )
    if selected_course:
        groups_list = groups_list.filter(course=selected_course)
    return render(
        request,
        "role_teacher/groups.html",
        {
            "courses": courses,
            "groups": groups_list,
            "selected_course": selected_course,
        },
    )


@teacher_required
def group_detail(request, group_id):
    user = request.current_user
    group = get_object_or_404(teacher_groups(user), pk=group_id)
    schedules = list(
        group.schedule_items
        .select_related("lesson", "lesson__module", "teacher")
        .order_by("lesson__module__sort_order", "lesson__sort_order", "start_at")
    )
    enrollments = list(
        group.enrollments
        .select_related("student")
        .filter(status="active")
        .order_by("student__last_name", "student__first_name")
    )

    if request.method == "POST" and request.POST.get("action") in {"save_attendance", "save_attendance_grid"}:
        valid_statuses = {choice[0] for choice in LessonAttendance.AttendanceStatus.choices}
        target_schedules = schedules
        if request.POST.get("action") == "save_attendance":
            target_schedule = get_object_or_404(group.schedule_items.all(), pk=request.POST.get("schedule"))
            target_schedules = [target_schedule]
        for schedule in target_schedules:
            for enrollment in enrollments:
                status = (
                    request.POST.get(f"student_{enrollment.student_id}_{schedule.id}")
                    or request.POST.get(f"student_{enrollment.student_id}")
                )
                if status not in valid_statuses:
                    continue
                attendance, _ = LessonAttendance.objects.get_or_create(
                    schedule=schedule,
                    student=enrollment.student,
                    defaults={"status": status},
                )
                attendance.status = status
                if status == LessonAttendance.AttendanceStatus.PRESENT and not attendance.joined_at:
                    attendance.joined_at = schedule.start_at
                    attendance.left_at = schedule.end_at
                attendance.save(update_fields=["status", "joined_at", "left_at"])
        return redirect("role_teacher:group_detail", group_id=group.id)

    attendance_map = {
        (attendance.student_id, attendance.schedule_id): attendance
        for attendance in LessonAttendance.objects.filter(schedule__in=schedules).select_related("student", "schedule")
    }
    for enrollment in enrollments:
        enrollment.attendance_cells = []
        for schedule in schedules:
            attendance = attendance_map.get((enrollment.student_id, schedule.id))
            enrollment.attendance_cells.append(
                {
                    "schedule": schedule,
                    "attendance": attendance,
                    "status": attendance.status if attendance else LessonAttendance.AttendanceStatus.ABSENT,
                }
            )

    module_headers = []
    for schedule in schedules:
        module_title = schedule.lesson.module.title if schedule.lesson and schedule.lesson.module else "Без модуля"
        if module_headers and module_headers[-1]["title"] == module_title:
            module_headers[-1]["colspan"] += 1
        else:
            module_headers.append({"title": module_title, "colspan": 1})

    return render(
        request,
        "role_teacher/group_detail.html",
        {
            "group": group,
            "enrollments": enrollments,
            "schedules": schedules,
            "module_headers": module_headers,
            "attendance_statuses": LessonAttendance.AttendanceStatus.choices,
        },
    )


@teacher_required
def schedule(request):
    user = request.current_user

    if request.method == "POST" and request.POST.get("action") == "update_status":
        schedule_item = get_object_or_404(
            Schedule,
            Q(teacher=user) | Q(group__in=teacher_groups(user)),
            pk=request.POST.get("schedule_id"),
        )
        status = request.POST.get("status")
        valid_statuses = {choice[0] for choice in Schedule.ScheduleStatus.choices}
        if status in valid_statuses:
            schedule_item.status = status
            schedule_item.is_visible_to_students = request.POST.get("is_visible_to_students") == "on"
            schedule_item.save(update_fields=["status", "is_visible_to_students", "updated_at"])
            if status == Schedule.ScheduleStatus.CANCELLED:
                notify_group(
                    schedule_item.group,
                    "Занятие отменено",
                    f'Занятие по курсу "{schedule_item.group.course.title}" отменено.',
                )
        return redirect("role_teacher:schedule")

    schedules = (
        Schedule.objects
        .filter(Q(teacher=user) | Q(group__in=teacher_groups(user)))
        .select_related("group", "group__course", "lesson", "teacher")
        .order_by("start_at")
        .distinct()
    )
    return render(
        request,
        "role_teacher/schedule.html",
        {
            "schedules": schedules,
            "statuses": Schedule.ScheduleStatus.choices,
            "soon_limit": timezone.now() + timedelta(days=7),
        },
    )


@teacher_required
def submissions(request):
    user = request.current_user

    if request.method == "POST" and request.POST.get("action") == "grade_submission":
        submission = get_object_or_404(teacher_submissions(user), pk=request.POST.get("submission_id"))
        try:
            score = int(request.POST.get("score", ""))
        except ValueError:
            score = -1
        if 0 <= score <= submission.assignment.max_score:
            submission.score = score
            submission.feedback = request.POST.get("feedback", "").strip()
            submission.status = StudentSubmission.SubmissionStatus.CHECKED
            submission.checked_at = timezone.now()
            submission.save(update_fields=["score", "feedback", "status", "checked_at"])
            Notification.objects.create(
                user=submission.student,
                title="Задание проверено",
                message=f'За задание "{submission.assignment.title}" выставлено {score}/{submission.assignment.max_score}.',
            )
        return submissions_redirect(request)

    mode = request.GET.get("mode", "assignments")
    if mode not in {"assignments", "tests"}:
        mode = "assignments"

    courses = teacher_courses(user).order_by("title")
    selected_course_id = request.GET.get("course", "").strip()
    selected_group_id = request.GET.get("group", "").strip()
    selected_student_id = request.GET.get("student", "").strip()

    selected_course = courses.filter(pk=selected_course_id).first() if selected_course_id.isdigit() else None
    groups = teacher_groups(user).order_by("course__title", "name")
    selected_group = None
    selected_student = None

    if selected_course:
        groups = groups.filter(course=selected_course)
    selected_group = groups.filter(pk=selected_group_id).first() if selected_group_id.isdigit() else None

    enrollments = (
        Enrollment.objects
        .filter(group__in=groups, status=Enrollment.EnrollmentStatus.ACTIVE)
        .select_related("student", "group", "group__course")
        .order_by("student__last_name", "student__first_name")
        .distinct()
    )
    if selected_group:
        enrollments = enrollments.filter(group=selected_group)
    selected_enrollment = enrollments.filter(student_id=selected_student_id).first() if selected_student_id.isdigit() else None
    selected_student = selected_enrollment.student if selected_enrollment else None

    submissions_list = teacher_submissions(user)
    if selected_course:
        submissions_list = submissions_list.filter(assignment__lesson__module__course=selected_course)
    if selected_group:
        submissions_list = submissions_list.filter(student__enrollments__group=selected_group)
    if selected_student:
        submissions_list = submissions_list.filter(student=selected_student)
    submissions_list = submissions_list.distinct()
    checked_submissions = submissions_list.filter(status=StudentSubmission.SubmissionStatus.CHECKED)
    unchecked_submissions = submissions_list.exclude(status=StudentSubmission.SubmissionStatus.CHECKED)

    attempts = (
        TestAttempt.objects
        .filter(test__lesson__module__course__in=teacher_courses(user))
        .select_related("student", "test", "test__lesson", "test__lesson__module", "test__lesson__module__course")
        .prefetch_related("student_answers__answer", "student_answers__question__answers")
        .order_by("-finished_at", "-started_at")
        .distinct()
    )
    if selected_course:
        attempts = attempts.filter(test__lesson__module__course=selected_course)
    if selected_group:
        attempts = attempts.filter(student__enrollments__group=selected_group)
    if selected_student:
        attempts = attempts.filter(student=selected_student)
    checked_attempts = attempts.exclude(status=TestAttempt.AttemptStatus.STARTED)
    unchecked_attempts = attempts.filter(status=TestAttempt.AttemptStatus.STARTED)

    mode_tabs = []
    for tab_mode, title in (("assignments", "Задания"), ("tests", "Тесты")):
        query = {"mode": tab_mode}
        if selected_course:
            query["course"] = selected_course.id
        if selected_group:
            query["group"] = selected_group.id
        if selected_student:
            query["student"] = selected_student.id
        mode_tabs.append(
            {
                "key": tab_mode,
                "title": title,
                "active": tab_mode == mode,
                "url": f"{reverse('role_teacher:submissions')}?{urlencode(query)}",
            }
        )

    return render(
        request,
        "role_teacher/submissions.html",
        {
            "mode": mode,
            "mode_tabs": mode_tabs,
            "courses": courses,
            "groups": groups,
            "enrollments": enrollments,
            "selected_course": selected_course,
            "selected_group": selected_group,
            "selected_student": selected_student,
            "submissions": submissions_list,
            "checked_submissions": checked_submissions,
            "unchecked_submissions": unchecked_submissions,
            "checked_attempts": checked_attempts,
            "unchecked_attempts": unchecked_attempts,
        },
    )


@teacher_required
def content(request):
    user = request.current_user
    valid_modes = {"materials", "assignments", "tests"}

    if request.method == "POST":
        action = request.POST.get("action")
        lesson_required_actions = {
            "create_material",
            "update_material",
            "delete_material",
            "create_assignment",
            "update_assignment",
            "delete_assignment",
            "create_test",
            "update_test",
            "delete_test",
            "reply_comment",
        }
        lesson = None
        if action in lesson_required_actions:
            lesson_id = request.POST.get("lesson", "")
            lesson = teacher_lessons(user).filter(pk=lesson_id).first() if str(lesson_id).isdigit() else None
            if not lesson:
                return content_redirect(request, error="Выберите занятие.")
        if action == "create_material":
            file = request.FILES.get("file")
            file_url = request.POST.get("file_url", "").strip()
            material_type = get_material_type(request.POST.get("material_type"))
            error = resource_error(file, file_url, "Добавьте файл или ссылку на материал.")
            if error:
                return content_redirect(request, error=error)
            material = Material(
                lesson=lesson,
                title=request.POST.get("title", "").strip(),
                description=request.POST.get("description", "").strip(),
                material_type=material_type,
                file=file,
                file_url=file_url,
            )
            material.full_clean()
            material.save()
            for group in lesson.module.course.groups.filter(is_active=True):
                notify_group(group, "Новый материал", f'В курсе "{lesson.module.course.title}" добавлен материал к занятию "{lesson.title}".')
        elif action == "update_material":
            material = get_object_or_404(teacher_materials(user), pk=request.POST.get("material_id"), lesson=lesson)
            file_url = request.POST.get("file_url", "").strip()
            uploaded_file = request.FILES.get("file")
            material_type = get_material_type(request.POST.get("material_type") or material.material_type)
            error = resource_error(uploaded_file or material.file, file_url, "Добавьте файл или ссылку на материал.")
            if error:
                return content_redirect(request, error=error)
            material.title = request.POST.get("title", "").strip()
            material.description = request.POST.get("description", "").strip()
            material.file_url = file_url
            if uploaded_file:
                material.file = uploaded_file
            material.material_type = material_type
            material.full_clean()
            material.save()
        elif action == "delete_material":
            get_object_or_404(teacher_materials(user), pk=request.POST.get("material_id"), lesson=lesson).delete()
        elif action == "create_assignment":
            try:
                max_score = max(1, int(request.POST.get("max_score") or 100))
            except ValueError:
                max_score = 100
            file = request.FILES.get("file")
            file_url = request.POST.get("file_url", "").strip()
            error = resource_error(file, file_url, "Добавьте файл или ссылку на задание.")
            if error:
                return content_redirect(request, error=error)
            assignment = Assignment(
                lesson=lesson,
                title=request.POST.get("title", "").strip(),
                description=request.POST.get("description", "").strip(),
                file=file,
                file_url=file_url,
                max_score=max_score,
                deadline=timezone.now() + timedelta(days=7),
            )
            assignment.full_clean()
            assignment.save()
        elif action == "update_assignment":
            assignment = get_object_or_404(teacher_assignments(user), pk=request.POST.get("assignment_id"), lesson=lesson)
            try:
                max_score = max(1, int(request.POST.get("max_score") or assignment.max_score))
            except ValueError:
                max_score = assignment.max_score
            file_url = request.POST.get("file_url", "").strip()
            uploaded_file = request.FILES.get("file")
            error = resource_error(uploaded_file or assignment.file, file_url, "Добавьте файл или ссылку на задание.")
            if error:
                return content_redirect(request, error=error)
            assignment.title = request.POST.get("title", "").strip()
            assignment.description = request.POST.get("description", "").strip()
            assignment.file_url = file_url
            assignment.max_score = max_score
            if uploaded_file:
                assignment.file = uploaded_file
            assignment.full_clean()
            assignment.save()
        elif action == "delete_assignment":
            get_object_or_404(teacher_assignments(user), pk=request.POST.get("assignment_id"), lesson=lesson).delete()
        elif action == "create_test":
            try:
                passing_score = min(100, max(1, int(request.POST.get("passing_score") or 70)))
            except ValueError:
                passing_score = 70
            try:
                max_attempts = max(1, int(request.POST.get("max_attempts") or 1))
            except ValueError:
                max_attempts = 1
            question_texts = request.POST.getlist("questions") or [request.POST.get("question", "")]
            correct_answers = request.POST.getlist("correct_answers") or [request.POST.get("correct_answer", "")]
            wrong_answers = request.POST.getlist("wrong_answers") or [request.POST.get("wrong_answer", "")]
            question_scores = request.POST.getlist("question_scores")
            prepared_questions = []
            for index, question_text in enumerate(question_texts):
                question_text = question_text.strip()
                correct_answer = correct_answers[index].strip() if index < len(correct_answers) else ""
                wrong_answer = wrong_answers[index].strip() if index < len(wrong_answers) else ""
                if not question_text and not correct_answer and not wrong_answer:
                    continue
                if not question_text or not correct_answer or not wrong_answer:
                    return content_redirect(request, error="Заполните вопрос, верный и неверный ответ для каждого вопроса.")
                try:
                    question_score = max(1, int(question_scores[index])) if index < len(question_scores) else 1
                except ValueError:
                    question_score = 1
                prepared_questions.append(
                    {
                        "text": question_text,
                        "correct_answer": correct_answer,
                        "wrong_answer": wrong_answer,
                        "score": question_score,
                    }
                )
            if not prepared_questions:
                return content_redirect(request, error="Добавьте хотя бы один вопрос к тесту.")
            test = Test.objects.create(
                lesson=lesson,
                title=request.POST.get("title", "").strip(),
                description=request.POST.get("description", "").strip(),
                passing_score=passing_score,
                max_attempts=max_attempts,
            )
            for index, question_data in enumerate(prepared_questions, start=1):
                question = TestQuestion.objects.create(
                    test=test,
                    question_text=question_data["text"],
                    question_type=TestQuestion.QuestionType.SINGLE,
                    score=question_data["score"],
                    sort_order=index,
                )
                TestAnswer.objects.create(question=question, answer_text=question_data["correct_answer"], is_correct=True)
                TestAnswer.objects.create(question=question, answer_text=question_data["wrong_answer"], is_correct=False)
        elif action == "update_test":
            test = get_object_or_404(teacher_tests(user), pk=request.POST.get("test_id"), lesson=lesson)
            try:
                passing_score = min(100, max(1, int(request.POST.get("passing_score") or test.passing_score)))
            except ValueError:
                passing_score = test.passing_score
            try:
                max_attempts = max(1, int(request.POST.get("max_attempts") or test.max_attempts))
            except ValueError:
                max_attempts = test.max_attempts
            test.title = request.POST.get("title", "").strip()
            test.description = request.POST.get("description", "").strip()
            test.passing_score = passing_score
            test.max_attempts = max_attempts
            test.save(update_fields=["title", "description", "passing_score", "max_attempts"])
        elif action == "delete_test":
            get_object_or_404(teacher_tests(user), pk=request.POST.get("test_id"), lesson=lesson).delete()
        elif action == "reply_comment":
            original_comment = get_object_or_404(LessonComment, pk=request.POST.get("comment_id"), lesson=lesson)
            text = request.POST.get("text", "").strip()
            if text:
                LessonComment.objects.create(lesson=lesson, user=user, text=f"{original_comment.user}: {text}")
                Notification.objects.create(
                    user=original_comment.user,
                    title="Ответ преподавателя",
                    message=f'Преподаватель ответил на комментарий к занятию "{lesson.title}".',
                )
        return content_redirect(request)

    mode = request.GET.get("mode", "materials")
    if mode not in valid_modes:
        mode = "materials"

    courses = teacher_courses(user).order_by("title")
    selected_course_id = request.GET.get("course", "").strip()
    selected_module_id = request.GET.get("module", "").strip()
    selected_lesson_id = request.GET.get("lesson", "").strip()

    selected_course = courses.filter(pk=selected_course_id).first() if selected_course_id.isdigit() else None
    selected_module = (
        CourseModule.objects
        .filter(course__in=courses, pk=selected_module_id)
        .select_related("course")
        .first()
        if selected_module_id.isdigit()
        else None
    )
    selected_lesson = (
        teacher_lessons(user)
        .filter(pk=selected_lesson_id)
        .select_related("module", "module__course")
        .prefetch_related("materials", "assignments", "tests", "comments__user")
        .first()
        if selected_lesson_id.isdigit()
        else None
    )
    if selected_lesson:
        selected_module = selected_lesson.module
        selected_course = selected_lesson.module.course
    elif selected_module:
        selected_course = selected_module.course

    modules = CourseModule.objects.none()
    lessons = Lesson.objects.none()
    if selected_course:
        modules = selected_course.modules.order_by("sort_order")
        lessons = (
            Lesson.objects
            .filter(module__course=selected_course)
            .select_related("module", "module__course")
            .prefetch_related("materials", "assignments", "tests", "comments__user")
            .order_by("module__sort_order", "sort_order")
        )
    if selected_module:
        lessons = lessons.filter(module=selected_module)
    available_lessons = teacher_lessons(user).prefetch_related("materials", "assignments", "tests", "comments__user")
    if selected_course:
        available_lessons = available_lessons.filter(module__course=selected_course)
    if selected_module:
        available_lessons = available_lessons.filter(module=selected_module)

    materials = filter_lesson_content(
        teacher_materials(user).select_related("lesson", "lesson__module", "lesson__module__course"),
        selected_course,
        selected_module,
        selected_lesson,
    ).order_by("lesson__module__course__title", "lesson__module__sort_order", "lesson__sort_order", "title")
    assignments = filter_lesson_content(
        teacher_assignments(user).select_related("lesson", "lesson__module", "lesson__module__course"),
        selected_course,
        selected_module,
        selected_lesson,
    ).order_by("lesson__module__course__title", "lesson__module__sort_order", "lesson__sort_order", "title")
    tests = filter_lesson_content(
        teacher_tests(user).select_related("lesson", "lesson__module", "lesson__module__course"),
        selected_course,
        selected_module,
        selected_lesson,
    ).order_by("lesson__module__course__title", "lesson__module__sort_order", "lesson__sort_order", "title")
    content_items = {
        "materials": materials,
        "assignments": assignments,
        "tests": tests,
    }[mode]

    mode_tabs = [
        {"key": "materials", "title": "Материалы"},
        {"key": "assignments", "title": "Задания"},
        {"key": "tests", "title": "Тесты"},
    ]
    for tab in mode_tabs:
        query = {"mode": tab["key"]}
        if selected_course:
            query["course"] = selected_course.id
        if selected_module:
            query["module"] = selected_module.id
        if selected_lesson:
            query["lesson"] = selected_lesson.id
        tab["url"] = f"{reverse('role_teacher:content')}?{urlencode(query)}#teacher-content-workspace"
        tab["active"] = tab["key"] == mode

    return render(
        request,
        "role_teacher/content.html",
        {
            "courses": courses,
            "modules": modules,
            "lessons": lessons,
            "available_lessons": available_lessons,
            "selected_course": selected_course,
            "selected_module": selected_module,
            "selected_lesson": selected_lesson,
            "mode": mode,
            "mode_tabs": mode_tabs,
            "content_items": content_items,
            "material_type_choices": Material.MaterialType.choices,
            "error": request.GET.get("error"),
        },
    )


@teacher_required
def notifications(request):
    user = request.current_user
    if request.method == "POST" and request.POST.get("action") == "mark_read":
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        return redirect("role_teacher:notifications")

    return render(
        request,
        "role_teacher/notifications.html",
        {
            "notifications": Notification.objects.filter(user=user).order_by("-created_at")[:50],
        },
    )
