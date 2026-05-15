from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from main.models import Application, ApplicationStatusHistory, Enrollment, Notification


STATUS_TITLES = {
    Application.ApplicationStatus.APPROVED: "Заявка одобрена",
    Application.ApplicationStatus.REJECTED: "Заявка отклонена",
    Application.ApplicationStatus.CANCELLED: "Заявка отменена",
}


@receiver(pre_save, sender=Application)
def remember_previous_application_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    instance._previous_status = (
        sender.objects
        .filter(pk=instance.pk)
        .values_list("status", flat=True)
        .first()
    )


@receiver(post_save, sender=Application)
def notify_application_status_change(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_previous_status", None)
    if created or previous_status == instance.status:
        return

    ApplicationStatusHistory.objects.create(
        application=instance,
        old_status=previous_status,
        new_status=instance.status,
        comment=instance.comment,
    )

    if instance.status == Application.ApplicationStatus.APPROVED:
        Enrollment.objects.get_or_create(
            student=instance.student,
            course=instance.course,
            defaults={
                "application": instance,
                "status": Enrollment.EnrollmentStatus.ACTIVE,
            },
        )

    title = STATUS_TITLES.get(instance.status)
    if title:
        Notification.objects.create(
            user=instance.student,
            title=title,
            message=f'Статус заявки на курс "{instance.course.title}" изменен.',
        )
