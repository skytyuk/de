from functools import wraps
from django.shortcuts import redirect
from .models import Users

SESSION_USER_ID_KEY = "user_id"

def get_current_user(request):
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    return Users.objects.select_related("role").filter(pk=user_id).first()

def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = get_current_user(request)
        if user is None:
            return redirect("main:login")
        request.current_user = user
        return view_func(request, *args, **kwargs)

    return wrapper