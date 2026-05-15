from pathlib import Path
from django.conf import settings
from .session_auth import get_current_user
from role_admin.permissions import is_admin_user
from role_teacher.permissions import is_teacher_user
from .models import Notification


def current_user(request):
    user = get_current_user(request)
    is_student = bool(user and user.role and user.role.name.strip().lower() == "student")
    is_admin = is_admin_user(user)
    is_teacher = is_teacher_user(user)
    notification_unread_count = (
        Notification.objects.filter(user=user, is_read=False).count()
        if user and (is_student or is_admin or is_teacher)
        else 0
    )
    return {
        "current_user": user,
        "is_student": is_student,
        "is_admin": is_admin,
        "is_teacher": is_teacher,
        "notification_unread_count": notification_unread_count,
    }


def asset_versions(request):
    static_root = Path(settings.BASE_DIR) / "static"
    asset_version = 1

    if static_root.exists():
        asset_version = max(
            (int(path.stat().st_mtime) for path in static_root.rglob("*") if path.is_file()),
            default=1,
        )

    return {"asset_version": asset_version}
