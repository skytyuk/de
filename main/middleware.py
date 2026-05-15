import logging

from django.core.cache import cache

from .services import sync_lesson_progress_for_due_schedules


logger = logging.getLogger(__name__)


class LessonProgressSyncMiddleware:
    cache_key = "main:lesson-progress-sync"
    interval_seconds = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if cache.add(self.cache_key, "1", timeout=self.interval_seconds):
            try:
                sync_lesson_progress_for_due_schedules()
            except Exception:
                logger.exception("Lesson progress sync failed.")

        return self.get_response(request)
