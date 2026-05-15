import re

from django import forms

from .models import Roles, Users


PASSWORD_MIN_LENGTH = 8
PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


def get_password_errors(password: str) -> list[str]:
    if not password:
        return []

    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов.")
    if not any(char.islower() for char in password):
        errors.append("Пароль должен содержать хотя бы одну строчную букву.")
    if not any(char.isupper() for char in password):
        errors.append("Пароль должен содержать хотя бы одну заглавную букву.")
    if not any(char.isdigit() for char in password):
        errors.append("Пароль должен содержать хотя бы одну цифру.")
    if all(char.isalnum() for char in password):
        errors.append("Пароль должен содержать хотя бы один специальный символ.")
    return errors


class LoginForm(forms.Form):
    email = forms.EmailField(label="Почта")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)


class RegistrationCodeForm(forms.Form):
    code = forms.CharField(
        label="Код подтверждения",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "maxlength": "6",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Введите 6 цифр из письма.")
        return code


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput, min_length=PASSWORD_MIN_LENGTH)
    password_confirm = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput,
    )
    accept_terms = forms.BooleanField(
        label="Я принимаю условия Пользовательского соглашения",
        required=True,
        error_messages={"required": "Необходимо принять условия Пользовательского соглашения."},
    )
    accept_privacy = forms.BooleanField(
        label="Я согласен на обработку персональных данных в соответствии с Политикой конфиденциальности",
        required=True,
        error_messages={"required": "Необходимо согласиться на обработку персональных данных."},
    )

    class Meta:
        model = Users
        fields = [
            "last_name",
            "first_name",
            "middle_name",
            "email",
            "phone",
            "image",
        ]
        labels = {
            "last_name": "Фамилия",
            "first_name": "Имя",
            "middle_name": "Отчество (необязательно)",
            "email": "Почта",
            "phone": "Телефон (необязательно)",
            "image": "Фото (необязательно)",
        }
        widgets = {
            "image": forms.FileInput(),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Users.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с такой почтой уже существует.")
        return email

    def _clean_name_field(self, field_name: str, field_label: str) -> str:
        value = (self.cleaned_data.get(field_name) or "").strip()
        if value and not value.isalpha():
            raise forms.ValidationError(f'Поле "{field_label}" не должно содержать цифры или специальные символы.')
        return value

    def clean_last_name(self):
        return self._clean_name_field("last_name", "Фамилия")

    def clean_first_name(self):
        return self._clean_name_field("first_name", "Имя")

    def clean_middle_name(self):
        return self._clean_name_field("middle_name", "Отчество")

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return None
        if not PHONE_PATTERN.fullmatch(phone):
            raise forms.ValidationError("Введите телефон в формате +79991234567 или 89991234567.")
        if Users.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Пользователь с таким телефоном уже существует.")
        return phone

    def clean_password(self):
        password = self.cleaned_data.get("password")
        errors = get_password_errors(password)
        if errors:
            raise forms.ValidationError(errors)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Пароли не совпадают.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = Roles.objects.get(name__iexact="student")
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Users
        fields = [
            "last_name",
            "first_name",
            "middle_name",
            "email",
            "phone",
            "image",
        ]
        labels = {
            "last_name": "Фамилия",
            "first_name": "Имя",
            "middle_name": "Отчество (необязательно)",
            "email": "Почта",
            "phone": "Телефон (необязательно)",
            "image": "Фото (необязательно)",
        }
        widgets = {
            "image": forms.FileInput(),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        duplicate = Users.objects.filter(email=email).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Пользователь с такой почтой уже существует.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            return None
        if not PHONE_PATTERN.fullmatch(phone):
            raise forms.ValidationError("Введите телефон в формате +79991234567 или 89991234567.")
        duplicate = Users.objects.filter(phone=phone).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Пользователь с таким телефоном уже существует.")
        return phone


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(label="Текущий пароль", widget=forms.PasswordInput)
    new_password = forms.CharField(label="Новый пароль", widget=forms.PasswordInput, min_length=PASSWORD_MIN_LENGTH)
    new_password_confirm = forms.CharField(label="Подтверждение нового пароля", widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]
        if not self.user.check_password(current_password):
            raise forms.ValidationError("Текущий пароль введен неверно.")
        return current_password

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        errors = get_password_errors(password)
        if errors:
            raise forms.ValidationError(errors)
        return password

    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get("current_password")
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")

        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error("new_password_confirm", "Пароли не совпадают.")

        if current_password and new_password and self.user.check_password(new_password):
            self.add_error(None, "Новый пароль должен отличаться от текущего.")

        return cleaned_data

    def save(self):
        self.user.set_password(self.cleaned_data["new_password"])
        self.user.save(update_fields=["password"])
        return self.user
