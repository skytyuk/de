from functools import wraps

from django.http import HttpResponseForbidden

from main.session_auth import login_required


ADMIN_ROLE_NAMES = {"admin", "administrator", "админ", "администратор"}


def is_admin_user(user):
    role_name = getattr(getattr(user, "role", None), "name", "")
    return role_name.strip().lower() in ADMIN_ROLE_NAMES


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin_user(request.current_user):
            return HttpResponseForbidden("Раздел доступен только администратору.")
        return view_func(request, *args, **kwargs)

    return login_required(wrapper)
