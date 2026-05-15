from django.core.management.base import BaseCommand

from main.services import sync_lesson_progress_for_due_schedules


class Command(BaseCommand):
    help = "Synchronizes lesson progress for started and finished visible lessons."

    def handle(self, *args, **options):
        updated = sync_lesson_progress_for_due_schedules()
        self.stdout.write(self.style.SUCCESS(f"Lesson progress synchronized: {updated} enrollment(s)."))
