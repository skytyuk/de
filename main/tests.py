from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import Roles, Users
from .session_auth import SESSION_USER_ID_KEY
from .views import PENDING_REGISTRATION_SESSION_KEY


SMALL_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,"
    b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)
IN_MEMORY_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
LOCMEM_EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


class AuthFlowTests(TestCase):
    def setUp(self):
        self.student_role, _ = Roles.objects.get_or_create(name="student")

    def create_user(self, **overrides):
        user = Users(
            last_name="Petrov",
            first_name="Petr",
            middle_name="Petrovich",
            email="petr@example.com",
            phone="+79990000001",
            role=self.student_role,
            **overrides,
        )
        user.set_password("Strongpass123!")
        user.save()
        return user

    def login_session(self, user):
        session = self.client.session
        session[SESSION_USER_ID_KEY] = user.id
        session.save()

    def make_image_file(self, name="avatar.gif"):
        return SimpleUploadedFile(name, SMALL_GIF, content_type="image/gif")

    def start_registration(self, **overrides):
        data = {
            "last_name": "Sidorov",
            "first_name": "Sidor",
            "middle_name": "",
            "email": "sidor@example.com",
            "phone": "+79990000002",
            "password": "Strongpass123!",
            "password_confirm": "Strongpass123!",
            "accept_terms": "on",
            "accept_privacy": "on",
        }
        data.update(overrides)
        return self.client.post(reverse("main:register"), data)

    def confirm_registration(self, code):
        return self.client.post(
            reverse("main:register"),
            {
                "action": "confirm_registration",
                "code": code,
            },
        )

    def test_register_sends_code_then_creates_user_and_logs_in(self):
        with self.settings(EMAIL_BACKEND=LOCMEM_EMAIL_BACKEND):
            response = self.start_registration()

            self.assertEqual(response.status_code, 200)
            self.assertFalse(Users.objects.filter(email="sidor@example.com").exists())
            pending_registration = self.client.session[PENDING_REGISTRATION_SESSION_KEY]
            self.assertEqual(len(mail.outbox), 1)
            self.assertIn(pending_registration["code"], mail.outbox[0].body)

            response = self.confirm_registration(pending_registration["code"])

        self.assertRedirects(response, reverse("main:profile"))
        user = Users.objects.get(email="sidor@example.com")
        self.assertEqual(self.client.session[SESSION_USER_ID_KEY], user.id)
        self.assertNotIn(PENDING_REGISTRATION_SESSION_KEY, self.client.session)

    def test_register_rejects_invalid_confirmation_code(self):
        with self.settings(EMAIL_BACKEND=LOCMEM_EMAIL_BACKEND):
            self.start_registration(email="wrong-code@example.com", phone="+79990000006")
            pending_registration = self.client.session[PENDING_REGISTRATION_SESSION_KEY]
            wrong_code = "000000" if pending_registration["code"] != "000000" else "111111"

            response = self.confirm_registration(wrong_code)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Users.objects.filter(email="wrong-code@example.com").exists())
        self.assertIn("code", response.context["code_form"].errors)

    def test_register_resends_new_confirmation_code(self):
        with self.settings(EMAIL_BACKEND=LOCMEM_EMAIL_BACKEND):
            with patch("main.views._generate_registration_code", side_effect=["111111", "222222"]):
                self.start_registration(email="resend@example.com", phone="+79990000007")
                first_code = self.client.session[PENDING_REGISTRATION_SESSION_KEY]["code"]

                response = self.client.post(
                    reverse("main:register"),
                    {
                        "action": "resend_registration_code",
                    },
                )

                second_code = self.client.session[PENDING_REGISTRATION_SESSION_KEY]["code"]

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["confirmation_modal_open"])
        self.assertNotEqual(first_code, second_code)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(second_code, mail.outbox[1].body)
        self.assertFalse(Users.objects.filter(email="resend@example.com").exists())

    def test_register_send_failure_shows_notification(self):
        with patch("main.views.send_mail", side_effect=RuntimeError("SMTP error")):
            response = self.start_registration(email="send-fail@example.com", phone="+79990000008")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["notification"])
        self.assertFalse(response.context["confirmation_modal_open"])
        self.assertFalse(response.context["form"].non_field_errors())
        self.assertFalse(Users.objects.filter(email="send-fail@example.com").exists())
        self.assertNotIn(PENDING_REGISTRATION_SESSION_KEY, self.client.session)

    def test_register_saves_image_in_user_folder_with_numbered_name(self):
        with self.settings(STORAGES=IN_MEMORY_STORAGES, EMAIL_BACKEND=LOCMEM_EMAIL_BACKEND):
            response = self.start_registration(
                email="image-user@example.com",
                phone="+79990000005",
                image=self.make_image_file(),
            )

            self.assertEqual(response.status_code, 200)
            pending_registration = self.client.session[PENDING_REGISTRATION_SESSION_KEY]
            response = self.confirm_registration(pending_registration["code"])

            self.assertRedirects(response, reverse("main:profile"))
            user = Users.objects.get(email="image-user@example.com")
            expected_name = f"user_images/id_{user.id}/1.gif"
            self.assertEqual(user.image.name, expected_name)
            self.assertTrue(default_storage.exists(expected_name))

    def test_register_rejects_name_fields_with_non_letters(self):
        response = self.client.post(
            reverse("main:register"),
            {
                "last_name": "Ivanov1",
                "first_name": "Ivan!",
                "middle_name": "Ivanovich-",
                "email": "bad-names@example.com",
                "phone": "+79990000004",
                "password": "Strongpass123!",
                "password_confirm": "Strongpass123!",
                "accept_terms": "on",
                "accept_privacy": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("last_name", form.errors)
        self.assertIn("first_name", form.errors)
        self.assertIn("middle_name", form.errors)
        self.assertFalse(Users.objects.filter(email="bad-names@example.com").exists())
        self.assertNotIn(PENDING_REGISTRATION_SESSION_KEY, self.client.session)

    def test_login_redirects_to_profile(self):
        self.create_user()

        response = self.client.post(
            reverse("main:login"),
            {
                "email": "petr@example.com",
                "password": "Strongpass123!",
            },
        )

        self.assertRedirects(response, reverse("main:profile"))

    def test_profile_requires_session(self):
        response = self.client.get(reverse("main:profile"))
        self.assertRedirects(response, reverse("main:login"))

    def test_profile_update_changes_user_data(self):
        user = self.create_user()
        self.login_session(user)

        response = self.client.post(
            reverse("main:profile"),
            {
                "action": "update_profile",
                "last_name": "Ivanov",
                "first_name": "Ivan",
                "middle_name": "",
                "email": "ivan@example.com",
                "phone": "+79990000003",
            },
        )

        self.assertRedirects(response, reverse("main:profile"))
        user.refresh_from_db()
        self.assertEqual(user.last_name, "Ivanov")
        self.assertEqual(user.first_name, "Ivan")
        self.assertFalse(user.middle_name)
        self.assertEqual(user.email, "ivan@example.com")
        self.assertEqual(user.phone, "+79990000003")

    def test_profile_image_upload_uses_next_number_in_user_folder(self):
        with self.settings(STORAGES=IN_MEMORY_STORAGES):
            user = self.create_user()
            self.login_session(user)
            default_storage.save(f"user_images/id_{user.id}/1.gif", ContentFile(SMALL_GIF))

            response = self.client.post(
                reverse("main:profile"),
                {
                    "action": "update_profile",
                    "last_name": user.last_name,
                    "first_name": user.first_name,
                    "middle_name": user.middle_name,
                    "email": user.email,
                    "phone": user.phone,
                    "image": self.make_image_file(),
                },
            )

            self.assertRedirects(response, reverse("main:profile"))
            user.refresh_from_db()
            expected_name = f"user_images/id_{user.id}/2.gif"
            self.assertEqual(user.image.name, expected_name)
            self.assertTrue(default_storage.exists(expected_name))

    def test_password_change_updates_credentials(self):
        user = self.create_user()
        self.login_session(user)

        response = self.client.post(
            reverse("main:profile"),
            {
                "action": "change_password",
                "current_password": "Strongpass123!",
                "new_password": "Newstrong123!",
                "new_password_confirm": "Newstrong123!",
            },
        )

        self.assertRedirects(response, reverse("main:profile"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("Newstrong123!"))

    def test_password_change_rejects_wrong_current_password(self):
        user = self.create_user()
        original_password_hash = user.password
        self.login_session(user)

        response = self.client.post(
            reverse("main:profile"),
            {
                "action": "change_password",
                "current_password": "Wrongpass123!",
                "new_password": "Newstrong123!",
                "new_password_confirm": "Newstrong123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        password_form = response.context["password_form"]
        self.assertIn("current_password", password_form.errors)
        self.assertNotIn("new_password", password_form.errors)
        user.refresh_from_db()
        self.assertEqual(user.password, original_password_hash)
        self.assertFalse(user.check_password("Newstrong123!"))

    def test_password_change_rejects_reused_password(self):
        user = self.create_user()
        original_password_hash = user.password
        self.login_session(user)

        response = self.client.post(
            reverse("main:profile"),
            {
                "action": "change_password",
                "current_password": "Strongpass123!",
                "new_password": "Strongpass123!",
                "new_password_confirm": "Strongpass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        password_form = response.context["password_form"]
        self.assertTrue(password_form.non_field_errors())
        self.assertNotIn("new_password", password_form.errors)
        user.refresh_from_db()
        self.assertEqual(user.password, original_password_hash)

    def test_delete_account_removes_user_and_logs_out(self):
        user = self.create_user()
        self.login_session(user)

        response = self.client.post(
            reverse("main:profile"),
            {
                "action": "delete_account",
            },
        )

        self.assertRedirects(response, reverse("main:index"))
        self.assertFalse(Users.objects.filter(pk=user.pk).exists())
        self.assertNotIn(SESSION_USER_ID_KEY, self.client.session)
