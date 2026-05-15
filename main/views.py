from pathlib import Path
import secrets
import time
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import LoginForm, PasswordChangeForm, ProfileUpdateForm, RegistrationCodeForm, RegistrationForm
from .models import Course, Notification, Roles, Users
from .session_auth import SESSION_USER_ID_KEY, get_current_user, login_required


PENDING_REGISTRATION_SESSION_KEY = "pending_registration"
REGISTRATION_CODE_TTL_SECONDS = 10 * 60
EMAIL_SEND_FAILURE_MESSAGE = "Не удалось отправить код подтверждения, попробуйте позже."


def index(request):
    featured_courses = (
        Course.objects
        .filter(is_active=True)
        .select_related("category")
        .order_by("title")[:4]
    )
    return render(request, "main/home.html", {"featured_courses": featured_courses})


@login_required
def notification_counts(request):
    return JsonResponse(
        {
            "unread": Notification.objects.filter(
                user=request.current_user,
                is_read=False,
            ).count()
        }
    )


@csrf_exempt
@require_POST
def load_test_create_role(request):
    if not settings.DEBUG:
        return JsonResponse({"error": "Not found"}, status=404)

    role = Roles.objects.create(name=f"load_role_{uuid.uuid4().hex[:12]}")
    return JsonResponse({"id": role.id, "name": role.name}, status=201)


def _generate_registration_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def _cleanup_pending_image(pending_registration):
    image_path = pending_registration.get("image_path")
    if image_path and default_storage.exists(image_path):
        default_storage.delete(image_path)


def _store_pending_image(request, image):
    if not image:
        return None

    if not request.session.session_key:
        request.session.create()

    extension = Path(image.name).suffix.lower()
    image_path = f"pending_registration/{request.session.session_key}/{uuid.uuid4().hex}{extension}"
    return default_storage.save(image_path, image)


def _build_pending_registration(request, form):
    previous_pending = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
    if previous_pending:
        _cleanup_pending_image(previous_pending)

    cleaned_data = form.cleaned_data
    return {
        "last_name": cleaned_data["last_name"],
        "first_name": cleaned_data["first_name"],
        "middle_name": cleaned_data.get("middle_name") or "",
        "email": cleaned_data["email"],
        "phone": cleaned_data.get("phone") or "",
        "password_hash": make_password(cleaned_data["password"]),
        "image_path": _store_pending_image(request, cleaned_data.get("image")),
        "code": _generate_registration_code(),
        "created_at": int(time.time()),
    }


def _send_registration_code(pending_registration):
    send_mail(
        "Код подтверждения регистрации",
        f"Ваш код подтверждения: {pending_registration['code']}",
        settings.DEFAULT_FROM_EMAIL,
        [pending_registration["email"]],
    )


def _pending_registration_is_expired(pending_registration):
    created_at = pending_registration.get("created_at", 0)
    return int(time.time()) - created_at > REGISTRATION_CODE_TTL_SECONDS


def _create_user_from_pending_registration(pending_registration):
    role = Roles.objects.get(name__iexact="student")
    user = Users(
        last_name=pending_registration["last_name"],
        first_name=pending_registration["first_name"],
        middle_name=pending_registration.get("middle_name") or None,
        email=pending_registration["email"],
        phone=pending_registration.get("phone") or None,
        role=role,
    )
    user.password = pending_registration["password_hash"]

    image_path = pending_registration.get("image_path")
    if image_path:
        with default_storage.open(image_path, "rb") as image_file:
            user.image = File(image_file, name=Path(image_path).name)
            user.save()
    else:
        user.save()

    return user


def register_view(request):
    if get_current_user(request):
        return redirect("main:profile")

    form = RegistrationForm()
    code_form = RegistrationCodeForm()
    confirmation_modal_open = False
    pending_email = None
    notification = None
    notification_preserve_scroll = False

    if request.method == "POST":
        action = request.POST.get("action", "start_registration")

        if action == "confirm_registration":
            code_form = RegistrationCodeForm(request.POST)
            pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
            pending_email = pending_registration["email"] if pending_registration else None
            confirmation_modal_open = True

            if not pending_registration:
                code_form.add_error(None, "Срок действия кода истек. Заполните регистрацию еще раз.")
            elif _pending_registration_is_expired(pending_registration):
                _cleanup_pending_image(pending_registration)
                request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                code_form.add_error(None, "Срок действия кода истек. Заполните регистрацию еще раз.")
            elif code_form.is_valid():
                code = code_form.cleaned_data["code"]
                if code != pending_registration["code"]:
                    code_form.add_error("code", "Неверный код подтверждения.")
                elif Users.objects.filter(email__iexact=pending_registration["email"]).exists():
                    code_form.add_error(None, "Пользователь с такой почтой уже существует.")
                    _cleanup_pending_image(pending_registration)
                    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                elif pending_registration.get("phone") and Users.objects.filter(phone=pending_registration["phone"]).exists():
                    code_form.add_error(None, "Пользователь с таким телефоном уже существует.")
                    _cleanup_pending_image(pending_registration)
                    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                else:
                    with transaction.atomic():
                        user = _create_user_from_pending_registration(pending_registration)
                    _cleanup_pending_image(pending_registration)
                    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                    request.session.cycle_key()
                    request.session[SESSION_USER_ID_KEY] = user.id
                    return redirect("main:profile")
        elif action == "resend_registration_code":
            pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
            if pending_registration and not _pending_registration_is_expired(pending_registration):
                pending_registration = {
                    **pending_registration,
                    "code": _generate_registration_code(),
                    "created_at": int(time.time()),
                }
                pending_email = pending_registration["email"]
                confirmation_modal_open = True
                try:
                    _send_registration_code(pending_registration)
                    request.session[PENDING_REGISTRATION_SESSION_KEY] = pending_registration
                except Exception:
                    notification = EMAIL_SEND_FAILURE_MESSAGE
                    notification_preserve_scroll = True
            else:
                if pending_registration:
                    _cleanup_pending_image(pending_registration)
                request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                notification = "Срок действия кода истек. Заполните регистрацию еще раз."
        else:
            form = RegistrationForm(request.POST, request.FILES or None)
            if form.is_valid():
                pending_registration = _build_pending_registration(request, form)
                request.session[PENDING_REGISTRATION_SESSION_KEY] = pending_registration
                pending_email = pending_registration["email"]
                confirmation_modal_open = True
                try:
                    _send_registration_code(pending_registration)
                except Exception:
                    _cleanup_pending_image(pending_registration)
                    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                    pending_email = None
                    confirmation_modal_open = False
                    notification = EMAIL_SEND_FAILURE_MESSAGE
                    notification_preserve_scroll = True

    return render(
        request,
        "main/auth/register.html",
        {
            "form": form,
            "code_form": code_form,
            "confirmation_modal_open": confirmation_modal_open,
            "pending_email": pending_email,
            "has_pending_registration": bool(request.session.get(PENDING_REGISTRATION_SESSION_KEY)),
            "notification": notification,
            "notification_preserve_scroll": notification_preserve_scroll,
        },
    )


def login_view(request):
    if get_current_user(request):
        return redirect("main:profile")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        password = form.cleaned_data["password"]
        user = Users.objects.select_related("role").filter(email=email).first()

        if user and user.check_password(password):
            request.session.cycle_key()
            request.session[SESSION_USER_ID_KEY] = user.id
            return redirect("main:profile")

        form.add_error(None, "Неверная почта или пароль.")

    return render(request, "main/auth/login.html", {"form": form})


def logout_view(request):
    request.session.flush()
    return redirect("main:index")


@login_required
def profile_view(request):
    user = request.current_user
    profile_form = ProfileUpdateForm(instance=user)
    password_form = PasswordChangeForm(user)
    password_modal_open = False

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_profile":
            profile_form = ProfileUpdateForm(request.POST, request.FILES or None, instance=user)
            password_form = PasswordChangeForm(user)
            if profile_form.is_valid():
                profile_form.save()
                return redirect("main:profile")
        elif action == "change_password":
            profile_form = ProfileUpdateForm(instance=user)
            password_form = PasswordChangeForm(user, request.POST)
            password_modal_open = True
            if password_form.is_valid():
                password_form.save()
                return redirect("main:profile")
        elif action == "delete_account":
            user.delete()
            request.session.flush()
            return redirect("main:index")

    return render(
        request,
        "main/profile.html",
        {
            "user": user,
            "profile_form": profile_form,
            "password_form": password_form,
            "password_modal_open": password_modal_open,
        },
    )
