from functools import wraps

from django.http import HttpResponseForbidden

from main.session_auth import login_required


TEACHER_ROLE_NAMES = {"teacher", "преподаватель", "учитель"}


def is_teacher_user(user):
    role_name = getattr(getattr(user, "role", None), "name", "")
    return role_name.strip().lower() in TEACHER_ROLE_NAMES


def teacher_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_teacher_user(request.current_user):
            return HttpResponseForbidden("Раздел доступен только преподавателю.")
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)
