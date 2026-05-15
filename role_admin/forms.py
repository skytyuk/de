from django import forms
from django.db import models
from django.forms import modelform_factory

from main.models import Users


ADMIN_FORM_EXCLUDED_FIELDS = {
    "enrollment": {"completed_at"},
    "lessonprogress": {"completed_at"},
    "supportticket": {"closed_at"},
    "studentsubmission": {"answer_text", "checked_at"},
    "testattempt": {"finished_at"},
}

ADMIN_FIELD_LABELS = {
    "schedulechange": {
        "reason": "Комментарий",
    },
    "studentsubmission": {
        "file_url": "URL",
    },
}

SINGLE_RESOURCE_MODELS = set()


class AdminBaseModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model_name = self._meta.model._meta.model_name
        for field_name, label in ADMIN_FIELD_LABELS.get(model_name, {}).items():
            if field_name in self.fields:
                self.fields[field_name].label = label
        for field_name, form_field in self.fields.items():
            model_field = self._meta.model._meta.get_field(field_name)
            if isinstance(model_field, models.DateTimeField):
                form_field.input_formats = ["%Y-%m-%dT%H:%M"]
            elif isinstance(model_field, models.DateField):
                form_field.input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned_data = super().clean()
        model_name = self._meta.model._meta.model_name
        if model_name not in SINGLE_RESOURCE_MODELS:
            return cleaned_data

        file_value = cleaned_data.get("file")
        url_value = (cleaned_data.get("file_url") or "").strip()
        has_file = bool(file_value)
        has_url = bool(url_value)

        if has_file and has_url:
            message = "Заполните только одно поле: файл или ссылку."
            self.add_error("file", message)
            self.add_error("file_url", message)
        elif not has_file and not has_url:
            message = "Добавьте файл или ссылку."
            self.add_error("file", message)
            self.add_error("file_url", message)

        return cleaned_data


class UsersDataForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Введите новый пароль. При редактировании оставьте пустым, чтобы не менять пароль.",
    )

    class Meta:
        model = Users
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["password"].required = True
            self.fields["password"].help_text = "Пароль будет сохранен в защищенном виде."
        else:
            self.initial["password"] = ""

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        elif user.pk:
            user.password = Users.objects.get(pk=user.pk).password
        if commit:
            user.save()
            self.save_m2m()
        return user


def get_model_form_class(model):
    if model is Users:
        return UsersDataForm
    model_name = model._meta.model_name
    excluded_fields = ADMIN_FORM_EXCLUDED_FIELDS.get(model_name, set())

    def get_editable_field_names(exclude=()):
        excluded = set(exclude) | excluded_fields
        field_names = [
            field.name
            for field in model._meta.fields
            if field.editable and field.name not in excluded
        ]
        field_names.extend(
            field.name
            for field in model._meta.many_to_many
            if field.editable and field.remote_field.through._meta.auto_created and field.name not in excluded
        )
        return field_names

    widgets = {
        field.name: forms.Textarea(attrs={"rows": 3})
        for field in model._meta.fields
        if isinstance(field, models.TextField)
    }
    for field in model._meta.fields:
        if isinstance(field, models.DateTimeField):
            widgets[field.name] = forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            )
        elif isinstance(field, models.DateField):
            widgets[field.name] = forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            )

    return modelform_factory(
        model,
        fields=get_editable_field_names(),
        form=AdminBaseModelForm,
        widgets=widgets,
    )
