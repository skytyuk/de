from django.utils import timezone

from .models import Enrollment, LessonProgress, Schedule, StudentSubmission, TestAttempt


def lesson_requirements_done(student, lesson):
    assignments = list(lesson.assignments.all())
    tests = list(lesson.tests.all())

    assignments_done = not assignments or (
        StudentSubmission.objects
        .filter(student=student, assignment__in=assignments)
        .count() >= len(assignments)
    )
    tests_done = not tests or (
        TestAttempt.objects
        .filter(student=student, test__in=tests)
        .exclude(status=TestAttempt.AttemptStatus.STARTED)
        .values("test_id")
        .distinct()
        .count() >= len(tests)
    )

    return assignments_done and tests_done


def refresh_lesson_progress(student, lesson, schedule=None, now=None):
    if not lesson:
        return None

    now = now or timezone.now()
    existing_progress = LessonProgress.objects.filter(student=student, lesson=lesson).first()
    if schedule and schedule.start_at > now:
        return existing_progress

    started_at = schedule.start_at if schedule and schedule.start_at <= now else now
    progress, _ = LessonProgress.objects.get_or_create(
        student=student,
        lesson=lesson,
        defaults={
            "status": LessonProgress.ProgressStatus.IN_PROGRESS,
            "started_at": started_at,
        },
    )

    lesson_finished = not schedule or schedule.end_at <= now
    if lesson_finished and lesson_requirements_done(student, lesson):
        progress.status = LessonProgress.ProgressStatus.COMPLETED
    else:
        progress.status = LessonProgress.ProgressStatus.IN_PROGRESS

    if not progress.started_at:
        progress.started_at = started_at

    progress.save(update_fields=["status", "started_at", "completed_at"])
    return progress


def sync_lesson_progress_for_due_schedules(now=None):
    now = now or timezone.now()
    schedules = (
        Schedule.objects
        .filter(start_at__lte=now, is_visible_to_students=True)
        .exclude(status=Schedule.ScheduleStatus.CANCELLED)
        .exclude(lesson__isnull=True)
        .select_related("group", "lesson")
        .prefetch_related("lesson__assignments", "lesson__tests")
    )

    updated = 0
    for schedule in schedules:
        enrollments = (
            Enrollment.objects
            .filter(group=schedule.group, status=Enrollment.EnrollmentStatus.ACTIVE)
            .select_related("student")
        )
        for enrollment in enrollments:
            refresh_lesson_progress(enrollment.student, schedule.lesson, schedule, now=now)
            updated += 1

    return updated
