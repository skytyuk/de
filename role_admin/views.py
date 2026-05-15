import csv
from itertools import chain
from urllib.parse import urlencode

from django.apps import apps
from django.core import serializers
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from main.models import (
    Application,
    Assignment,
    Certificate,
    Course,
    CourseCategory,
    CourseModule,
    CourseReview,
    CourseTag,
    Enrollment,
    Lesson,
    LessonAttendance,
    LessonComment,
    LessonProgress,
    Material,
    Notification,
    Payment,
    Schedule,
    ScheduleChange,
    StudyGroup,
    StudentSubmission,
    SupportMessage,
    SupportTicket,
    TeacherAvailability,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    Users,
)

from .forms import get_model_form_class
from .permissions import admin_required


PAGE_SIZE = 40

TABLE_DESCRIPTIONS = {
    "roles": "Роли пользователей: студент, преподаватель, администратор.",
    "users": "Пользователи системы, их контакты, аватарки и роль.",
    "coursecategory": "Категории курсов для группировки направлений обучения.",
    "coursetag": "Теги курсов для быстрого поиска и фильтрации каталога.",
    "coursetagrelation": "Связь многие-ко-многим между курсами и тегами.",
    "course": "Основная карточка курса: описание, уровень, стоимость и длительность.",
    "courseteacher": "Связь курсов с преподавателями, которые могут вести обучение.",
    "studygroup": "Учебные группы внутри курса с конкретным преподавателем и датами обучения.",
    "coursemodule": "Модули курса, из которых строится учебная программа.",
    "lesson": "Занятия внутри модулей курса: онлайн-занятия и оффлайн-занятия.",
    "material": "Материалы занятия: файл, ссылка или видео для студента.",
    "application": "Заявки студентов на курсы и их текущий статус обработки.",
    "applicationstatushistory": "История смены статусов заявок администратором.",
    "enrollment": "Зачисления студентов на курсы и привязка к учебной группе.",
    "teacheravailability": "Доступность преподавателей для составления расписания.",
    "schedule": "Расписание онлайн-занятий, коды встреч и публикация для студентов.",
    "schedulechange": "История переносов и изменений расписания.",
    "lessonattendance": "Посещаемость студентов на онлайн-занятиях.",
    "assignment": "Практические задания к занятиям, включая файл или ссылку.",
    "studentsubmission": "Ответы студентов на задания, оценки и комментарии преподавателя.",
    "test": "Тесты к занятиям с проходным баллом и количеством попыток.",
    "testquestion": "Вопросы тестов.",
    "testanswer": "Варианты ответов на вопросы тестов.",
    "testattempt": "Попытки прохождения тестов студентами и результат.",
    "studenttestanswer": "Ответы студента внутри конкретной попытки теста.",
    "lessonprogress": "Прогресс студента по занятиям курса.",
    "lessoncomment": "Комментарии и вопросы студентов к занятиям.",
    "payment": "Оплаты курсов студентами.",
    "certificate": "Сертификаты студентов после завершения курса.",
    "notification": "Уведомления пользователей: заявки, занятия, оценки, ответы.",
    "coursereview": "Отзывы и оценки курсов студентами.",
    "supportticket": "Обращения пользователей в поддержку.",
    "supportmessage": "Сообщения внутри обращений в поддержку.",
}

HIDDEN_TABLE_COLUMNS = {
    "studentsubmission": {"answer_text"},
}

COLUMN_LABELS = {
    "schedulechange": {
        "reason": "Комментарий",
    },
    "studentsubmission": {
        "file_url": "url",
    },
}

SEARCH_PLACEHOLDERS = {
    "roles": "ID или название роли",
    "users": "ID, почта или телефон",
    "coursecategory": "ID или название категории",
    "coursetag": "ID или название тега",
    "course": "ID или название курса",
    "studygroup": "ID или название группы",
    "coursemodule": "ID или название модуля",
    "lesson": "ID или название занятия",
    "material": "ID или название материала",
    "applicationstatushistory": "ID или имя того, кто изменил статус",
    "schedulechange": "ID или имя того, кто изменил расписание",
}

FILTER_PARAM_NAMES = (
    "active",
    "assignment",
    "category",
    "course",
    "group",
    "is_correct",
    "is_read",
    "lesson",
    "lesson_type",
    "level",
    "module",
    "question_type",
    "rating",
    "schedule",
    "status",
    "student",
    "tag",
    "teacher",
    "test",
    "ticket",
    "user",
)

COLLAPSIBLE_FILTER_TABLES = {
    "course",
    "studygroup",
    "lesson",
    "material",
    "enrollment",
    "schedule",
    "lessonattendance",
    "studentsubmission",
    "payment",
    "test",
    "testattempt",
}

WEEKDAY_LABELS = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}


def get_managed_models():
    return [
        model
        for model in apps.get_app_config("main").get_models()
        if model._meta.managed
    ]


def get_model_registry():
    return {
        model._meta.model_name: model
        for model in get_managed_models()
    }


def get_model_or_404(model_name):
    model = get_model_registry().get(model_name)
    if model is None:
        raise Http404("Таблица не найдена.")
    return model


def get_database_name():
    return connection.settings_dict.get("NAME", "")


def get_database_engine():
    return connection.settings_dict.get("ENGINE", "").rsplit(".", 1)[-1]


def get_table_meta():
    tables = []
    for model in get_managed_models():
        tables.append(
            {
                "model_name": model._meta.model_name,
                "verbose_name": model._meta.verbose_name_plural,
                "db_table": model._meta.db_table,
                "count": model.objects.count(),
                "description": TABLE_DESCRIPTIONS.get(model._meta.model_name, "Системная таблица проекта."),
            }
        )
    return tables


def get_display_fields(model):
    hidden_columns = HIDDEN_TABLE_COLUMNS.get(model._meta.model_name, set())
    return [
        field
        for field in model._meta.concrete_fields
        if field.name not in hidden_columns and field.attname not in hidden_columns
    ]


def format_field_value(obj, field):
    if field.name == "password":
        return "********"
    if obj._meta.model_name == "teacheravailability" and field.name == "day_of_week":
        value = field.value_from_object(obj)
        return f"{value} ({WEEKDAY_LABELS.get(value, 'день не указан')})"
    if field.get_internal_type() in {"FileField", "ImageField"}:
        file_value = getattr(obj, field.name, None)
        if file_value:
            try:
                return format_html(
                    '<a href="{}" target="_blank" rel="noopener">{}</a>',
                    file_value.url,
                    file_value.name,
                )
            except ValueError:
                return str(file_value)
        return "-"
    if field.is_relation:
        related = getattr(obj, field.name, None)
        return f"{related} (id_{related.pk})" if related else "-"
    if field.choices:
        display = getattr(obj, f"get_{field.name}_display", None)
        if display:
            return display()
    value = field.value_from_object(obj)
    if value in (None, ""):
        return "-"
    return str(value)


def get_column_label(field):
    return COLUMN_LABELS.get(field.model._meta.model_name, {}).get(field.name, field.attname)


def build_rows(objects, fields):
    return [
        {
            "object": obj,
            "values": [format_field_value(obj, field) for field in fields],
        }
        for obj in objects
    ]


def search_objects(model_name, objects, query):
    if not query:
        return objects

    query_filter = Q()
    if query.isdigit():
        query_filter |= Q(pk=int(query))

    if model_name == "roles":
        query_filter |= Q(name__icontains=query)
    elif model_name == "users":
        query_filter |= Q(email__icontains=query) | Q(phone__icontains=query)
    elif model_name == "coursecategory":
        query_filter |= Q(name__icontains=query)
    elif model_name == "coursetag":
        query_filter |= Q(name__icontains=query)
    elif model_name == "course":
        query_filter |= Q(title__icontains=query)
    elif model_name == "studygroup":
        query_filter |= Q(name__icontains=query)
    elif model_name == "coursemodule":
        query_filter |= Q(title__icontains=query)
    elif model_name == "lesson":
        query_filter |= Q(title__icontains=query)
    elif model_name == "material":
        query_filter |= Q(title__icontains=query)
    elif model_name == "applicationstatushistory":
        if query.isdigit():
            query_filter |= Q(changed_by_id=int(query))
        query_filter |= (
            Q(changed_by__first_name__icontains=query)
            | Q(changed_by__last_name__icontains=query)
            | Q(changed_by__middle_name__icontains=query)
            | Q(changed_by__email__icontains=query)
        )
    elif model_name == "schedulechange":
        if query.isdigit():
            query_filter |= Q(changed_by_id=int(query))
        query_filter |= (
            Q(changed_by__first_name__icontains=query)
            | Q(changed_by__last_name__icontains=query)
            | Q(changed_by__middle_name__icontains=query)
            | Q(changed_by__email__icontains=query)
        )

    return objects.filter(query_filter) if query_filter else objects


def option_items(items, selected_value):
    selected_value = str(selected_value or "")
    return [
        {
            "value": str(value),
            "label": label,
            "selected": str(value) == selected_value,
        }
        for value, label in items
    ]


def user_options(role_name=None):
    users = Users.objects.select_related("role").order_by("last_name", "first_name", "id")
    if role_name:
        users = users.filter(role__name__iexact=role_name)
    return [(user.id, f"{user} (id_{user.id})") for user in users]


def course_options():
    return [(course.id, f"{course.title} (id_{course.id})") for course in Course.objects.order_by("title")]


def group_options(course_id=None):
    groups = StudyGroup.objects.select_related("course").order_by("course__title", "name", "id")
    if course_id and str(course_id).isdigit():
        groups = groups.filter(course_id=course_id)
    return [(group.id, f"{group.course.title} — {group.name} (id_{group.id})") for group in groups]


def module_options(course_id=None):
    modules = CourseModule.objects.select_related("course").order_by("course__title", "sort_order", "title")
    if course_id and str(course_id).isdigit():
        modules = modules.filter(course_id=course_id)
    return [(module.id, f"{module.course.title} — {module.title} (id_{module.id})") for module in modules]


def lesson_options(course_id=None, module_id=None):
    lessons = Lesson.objects.select_related("module", "module__course").order_by(
        "module__course__title",
        "module__sort_order",
        "sort_order",
        "title",
    )
    if course_id and str(course_id).isdigit():
        lessons = lessons.filter(module__course_id=course_id)
    if module_id and str(module_id).isdigit():
        lessons = lessons.filter(module_id=module_id)
    return [(lesson.id, f"{lesson.module.course.title} — {lesson.title} (id_{lesson.id})") for lesson in lessons]


def schedule_options():
    schedules = Schedule.objects.select_related("group", "lesson").order_by("-start_at", "id")
    return [
        (
            schedule.id,
            f"{schedule.group} — {timezone.localtime(schedule.start_at).strftime('%d.%m.%Y %H:%M')} (id_{schedule.id})",
        )
        for schedule in schedules
    ]


def ticket_options():
    return [(ticket.id, f"{ticket.subject} (id_{ticket.id})") for ticket in SupportTicket.objects.order_by("subject", "id")]


def assignment_options():
    assignments = Assignment.objects.select_related("lesson", "lesson__module", "lesson__module__course").order_by(
        "lesson__module__course__title",
        "lesson__module__sort_order",
        "lesson__sort_order",
        "title",
    )
    return [
        (assignment.id, f"{assignment.lesson.module.course.title} — {assignment.title} (id_{assignment.id})")
        for assignment in assignments
    ]


def test_options():
    tests = Test.objects.select_related("lesson", "lesson__module", "lesson__module__course").order_by(
        "lesson__module__course__title",
        "lesson__module__sort_order",
        "lesson__sort_order",
        "title",
    )
    return [(test.id, f"{test.lesson.module.course.title} — {test.title} (id_{test.id})") for test in tests]


def boolean_options(true_label="Да", false_label="Нет"):
    return [("1", true_label), ("0", false_label)]


def get_table_filters(model_name, selected):
    filters = []

    def add_filter(name, label, options):
        filters.append(
            {
                "name": name,
                "label": label,
                "selected": selected.get(name, ""),
                "options": option_items(options, selected.get(name, "")),
            }
        )

    if model_name == "course":
        add_filter("category", "Категория", [(category.id, category.name) for category in CourseCategory.objects.order_by("name")])
        add_filter("tag", "Тег", [(tag.id, tag.name) for tag in CourseTag.objects.order_by("name")])
        add_filter("level", "Уровень", Course.CourseLevel.choices)
        add_filter("active", "Активность", boolean_options("Активные", "Неактивные"))
    elif model_name == "courseteacher":
        add_filter("course", "Курс", course_options())
        add_filter("teacher", "Учитель", user_options("teacher"))
    elif model_name == "coursetagrelation":
        add_filter("course", "Курс", course_options())
        add_filter("tag", "Тег", [(tag.id, tag.name) for tag in CourseTag.objects.order_by("name")])
    elif model_name == "studygroup":
        add_filter("course", "Курс", course_options())
        add_filter("teacher", "Учитель", user_options("teacher"))
    elif model_name == "coursemodule":
        add_filter("course", "Курс", course_options())
    elif model_name == "lesson":
        add_filter("course", "Курс", course_options())
        add_filter("module", "Модуль", module_options(selected.get("course")))
        add_filter("lesson_type", "Тип занятия", Lesson.LessonType.choices)
    elif model_name in {"material", "assignment"}:
        add_filter("course", "Курс", course_options())
        add_filter("module", "Модуль", module_options(selected.get("course")))
    elif model_name == "application":
        add_filter("student", "Студент", user_options("student"))
        add_filter("course", "Курс", course_options())
        add_filter("status", "Статус", Application.ApplicationStatus.choices)
    elif model_name == "enrollment":
        add_filter("student", "Студент", user_options("student"))
        add_filter("course", "Курс", course_options())
        add_filter("group", "Группа", group_options(selected.get("course")))
        add_filter("status", "Статус", Enrollment.EnrollmentStatus.choices)
    elif model_name == "teacheravailability":
        add_filter("teacher", "Учитель", user_options("teacher"))
    elif model_name == "schedule":
        add_filter("group", "Группа", group_options())
        add_filter("teacher", "Учитель", user_options("teacher"))
        add_filter("status", "Статус", Schedule.ScheduleStatus.choices)
    elif model_name == "schedulechange":
        add_filter("schedule", "Расписание", schedule_options())
    elif model_name == "lessonattendance":
        add_filter("schedule", "Расписание", schedule_options())
        add_filter("student", "Студент", user_options("student"))
        add_filter("status", "Статус", LessonAttendance.AttendanceStatus.choices)
    elif model_name == "studentsubmission":
        add_filter("assignment", "Задание", assignment_options())
        add_filter("student", "Студент", user_options("student"))
        add_filter("status", "Статус", StudentSubmission.SubmissionStatus.choices)
    elif model_name == "certificate":
        add_filter("student", "Студент", user_options("student"))
        add_filter("course", "Курс", course_options())
    elif model_name == "payment":
        add_filter("student", "Студент", user_options("student"))
        add_filter("course", "Курс", course_options())
        add_filter("status", "Статус", Payment.PaymentStatus.choices)
    elif model_name == "lessonprogress":
        add_filter("student", "Студент", user_options("student"))
        add_filter("lesson", "Занятие", lesson_options())
    elif model_name == "lessoncomment":
        add_filter("user", "Пользователь", user_options())
        add_filter("lesson", "Занятие", lesson_options())
    elif model_name == "test":
        add_filter("course", "Курс", course_options())
        add_filter("module", "Модуль", module_options(selected.get("course")))
        add_filter("lesson", "Занятие", lesson_options(selected.get("course"), selected.get("module")))
    elif model_name == "testquestion":
        add_filter("test", "Тест", test_options())
        add_filter("question_type", "Тип вопроса", TestQuestion.QuestionType.choices)
    elif model_name == "testanswer":
        add_filter("test", "Тест", test_options())
        add_filter("is_correct", "Вариант ответа", boolean_options("Верный", "Неверный"))
    elif model_name == "testattempt":
        add_filter("test", "Тест", test_options())
        add_filter("student", "Студент", user_options("student"))
        add_filter("status", "Статус", TestAttempt.AttemptStatus.choices)
    elif model_name == "coursereview":
        add_filter("student", "Студент", user_options("student"))
        add_filter("course", "Курс", course_options())
        add_filter("rating", "Рейтинг", [(value, value) for value in range(1, 6)])
    elif model_name == "notification":
        add_filter("user", "Пользователь", user_options())
        add_filter("is_read", "Прочитано", boolean_options("Прочитано", "Не прочитано"))
    elif model_name == "supportticket":
        add_filter("user", "Пользователь", user_options())
        add_filter("status", "Статус", SupportTicket.TicketStatus.choices)
    elif model_name == "supportmessage":
        add_filter("ticket", "Тикет", ticket_options())
        add_filter("user", "Пользователь", user_options())

    return filters


def apply_boolean_filter(objects, field_name, value):
    if value == "1":
        return objects.filter(**{field_name: True})
    if value == "0":
        return objects.filter(**{field_name: False})
    return objects


def apply_table_filters(model_name, objects, selected):
    if model_name == "course":
        if selected.get("category"):
            objects = objects.filter(category_id=selected["category"])
        if selected.get("tag"):
            objects = objects.filter(tags__id=selected["tag"])
        if selected.get("level"):
            objects = objects.filter(level=selected["level"])
        objects = apply_boolean_filter(objects, "is_active", selected.get("active"))
    elif model_name == "courseteacher":
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("teacher"):
            objects = objects.filter(teacher_id=selected["teacher"])
    elif model_name == "coursetagrelation":
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("tag"):
            objects = objects.filter(tag_id=selected["tag"])
    elif model_name == "studygroup":
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("teacher"):
            objects = objects.filter(teacher_id=selected["teacher"])
    elif model_name == "coursemodule":
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
    elif model_name == "lesson":
        if selected.get("course"):
            objects = objects.filter(module__course_id=selected["course"])
        if selected.get("module"):
            objects = objects.filter(module_id=selected["module"])
        if selected.get("lesson_type"):
            objects = objects.filter(lesson_type=selected["lesson_type"])
    elif model_name in {"material", "assignment"}:
        if selected.get("course"):
            objects = objects.filter(lesson__module__course_id=selected["course"])
        if selected.get("module"):
            objects = objects.filter(lesson__module_id=selected["module"])
    elif model_name == "application":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "enrollment":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("group"):
            objects = objects.filter(group_id=selected["group"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "teacheravailability":
        if selected.get("teacher"):
            objects = objects.filter(teacher_id=selected["teacher"])
    elif model_name == "schedule":
        if selected.get("group"):
            objects = objects.filter(group_id=selected["group"])
        if selected.get("teacher"):
            objects = objects.filter(teacher_id=selected["teacher"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "schedulechange":
        if selected.get("schedule"):
            objects = objects.filter(schedule_id=selected["schedule"])
    elif model_name == "lessonattendance":
        if selected.get("schedule"):
            objects = objects.filter(schedule_id=selected["schedule"])
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "studentsubmission":
        if selected.get("assignment"):
            objects = objects.filter(assignment_id=selected["assignment"])
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "certificate":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
    elif model_name == "payment":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "lessonprogress":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("lesson"):
            objects = objects.filter(lesson_id=selected["lesson"])
    elif model_name == "lessoncomment":
        if selected.get("user"):
            objects = objects.filter(user_id=selected["user"])
        if selected.get("lesson"):
            objects = objects.filter(lesson_id=selected["lesson"])
    elif model_name == "test":
        if selected.get("course"):
            objects = objects.filter(lesson__module__course_id=selected["course"])
        if selected.get("module"):
            objects = objects.filter(lesson__module_id=selected["module"])
        if selected.get("lesson"):
            objects = objects.filter(lesson_id=selected["lesson"])
    elif model_name == "testquestion":
        if selected.get("test"):
            objects = objects.filter(test_id=selected["test"])
        if selected.get("question_type"):
            objects = objects.filter(question_type=selected["question_type"])
    elif model_name == "testanswer":
        if selected.get("test"):
            objects = objects.filter(question__test_id=selected["test"])
        objects = apply_boolean_filter(objects, "is_correct", selected.get("is_correct"))
    elif model_name == "testattempt":
        if selected.get("test"):
            objects = objects.filter(test_id=selected["test"])
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "coursereview":
        if selected.get("student"):
            objects = objects.filter(student_id=selected["student"])
        if selected.get("course"):
            objects = objects.filter(course_id=selected["course"])
        if selected.get("rating"):
            objects = objects.filter(rating=selected["rating"])
    elif model_name == "notification":
        if selected.get("user"):
            objects = objects.filter(user_id=selected["user"])
        objects = apply_boolean_filter(objects, "is_read", selected.get("is_read"))
    elif model_name == "supportticket":
        if selected.get("user"):
            objects = objects.filter(user_id=selected["user"])
        if selected.get("status"):
            objects = objects.filter(status=selected["status"])
    elif model_name == "supportmessage":
        if selected.get("ticket"):
            objects = objects.filter(ticket_id=selected["ticket"])
        if selected.get("user"):
            objects = objects.filter(sender_id=selected["user"])

    return objects.distinct()


def redirect_with_query(url_name, *args, query=None, kwargs=None):
    url = reverse(url_name, args=args, kwargs=kwargs)
    if query:
        url = f"{url}?{urlencode(query)}"
    return redirect(url)


def table_redirect(model, base_query=None, **query):
    redirect_query = {}
    if base_query:
        redirect_query.update(
            {
                key: value
                for key, value in base_query.items()
                if key not in {"notice", "error"}
            }
        )
    redirect_query.update({key: value for key, value in query.items() if value})
    return redirect_with_query(
        "role_admin:table_detail",
        model._meta.model_name,
        query=redirect_query,
    )


def query_from_string(query_string):
    query = QueryDict(query_string or "", mutable=True)
    query.pop("notice", None)
    query.pop("error", None)
    return query


def get_teacher_queryset():
    return Users.objects.select_related("role").filter(role__name__iexact="teacher").order_by("last_name", "first_name")


def parse_datetime_input(value):
    parsed_value = parse_datetime(value or "")
    if parsed_value is None:
        raise ValidationError("Введите корректную дату и время.")
    if timezone.is_naive(parsed_value):
        parsed_value = timezone.make_aware(parsed_value, timezone.get_current_timezone())
    return parsed_value


def notify_group_students(group, title, message):
    notifications = [
        Notification(user=enrollment.student, title=title, message=message)
        for enrollment in group.enrollments.select_related("student").filter(status=Enrollment.EnrollmentStatus.ACTIVE)
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


def get_uploaded_json(request):
    uploaded_file = request.FILES.get("fixture")
    if not uploaded_file:
        raise ValidationError("Выберите JSON-файл для загрузки.")
    return uploaded_file.read().decode("utf-8-sig")


def deserialize_objects(payload, expected_model=None):
    objects = list(serializers.deserialize("json", payload))
    if expected_model:
        expected_label = expected_model._meta.label_lower
        for item in objects:
            if item.object._meta.label_lower != expected_label:
                raise ValidationError("В файле есть записи не из этой таблицы.")
    return objects


def save_deserialized_objects(objects):
    count = 0
    for item in objects:
        item.save()
        count += 1
    return count


@admin_required
def dashboard(request):
    tables = get_table_meta()
    total_records = sum(table["count"] for table in tables)
    return render(
        request,
        "role_admin/dashboard.html",
        {
            "database_name": get_database_name(),
            "database_engine": get_database_engine(),
            "tables_count": len(tables),
            "total_records": total_records,
            "tables": tables[:8],
        },
    )


@admin_required
def education_overview(request):
    now = timezone.now()
    groups = (
        StudyGroup.objects
        .select_related("course", "teacher")
        .annotate(students_count=Count("enrollments", filter=Q(enrollments__status=Enrollment.EnrollmentStatus.ACTIVE)))
        .order_by("course__title", "name")[:8]
    )
    courses = (
        Course.objects
        .filter(is_active=True)
        .select_related("category")
        .annotate(
            modules_count=Count("modules", distinct=True),
            lessons_count=Count("modules__lessons", distinct=True),
            groups_count=Count("groups", distinct=True),
        )
        .order_by("title")[:8]
    )
    schedules = (
        Schedule.objects
        .filter(start_at__gte=now)
        .select_related("group", "group__course", "lesson", "teacher")
        .order_by("start_at")[:10]
    )

    return render(
        request,
        "role_admin/education.html",
        {
            "applications_count": Application.objects.filter(status=Application.ApplicationStatus.NEW).count(),
            "active_groups_count": StudyGroup.objects.filter(is_active=True).count(),
            "active_enrollments_count": Enrollment.objects.filter(status=Enrollment.EnrollmentStatus.ACTIVE).count(),
            "planned_lessons_count": Schedule.objects.filter(status=Schedule.ScheduleStatus.PLANNED, start_at__gte=now).count(),
            "groups": groups,
            "courses": courses,
            "schedules": schedules,
        },
    )


@admin_required
def notifications(request):
    user = request.current_user
    if request.method == "POST" and request.POST.get("action") == "mark_read":
        Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        return redirect("role_admin:notifications")

    return render(
        request,
        "role_admin/notifications.html",
        {
            "notifications": Notification.objects.filter(user=user).order_by("-created_at")[:50],
        },
    )


@admin_required
def applications(request):
    notice = None
    error = None

    if request.method == "POST":
        application = get_object_or_404(Application, pk=request.POST.get("application_id"))
        status = request.POST.get("status")
        valid_statuses = {choice[0] for choice in Application.ApplicationStatus.choices}

        if status not in valid_statuses:
            error = "Выбран неверный статус заявки."
        else:
            selected_group = None
            group_id = request.POST.get("group")
            if group_id:
                selected_group = get_object_or_404(StudyGroup, pk=group_id, course=application.course)

            application.status = status
            application.comment = request.POST.get("comment", "").strip()
            application.save(update_fields=["status", "comment", "updated_at"])
            if status == Application.ApplicationStatus.APPROVED:
                enrollment, _ = Enrollment.objects.get_or_create(
                    student=application.student,
                    course=application.course,
                    defaults={
                        "application": application,
                        "status": Enrollment.EnrollmentStatus.ACTIVE,
                    },
                )
                enrollment.application = application
                enrollment.status = Enrollment.EnrollmentStatus.ACTIVE
                if selected_group:
                    enrollment.group = selected_group
                enrollment.save(update_fields=["application", "status", "group"])
            elif status in {Application.ApplicationStatus.REJECTED, Application.ApplicationStatus.CANCELLED}:
                Enrollment.objects.filter(student=application.student, course=application.course).update(
                    status=Enrollment.EnrollmentStatus.CANCELLED,
                    completed_at=timezone.now(),
                )
            notice = "Заявка обработана."

    applications_list = (
        Application.objects
        .select_related("student", "course")
        .prefetch_related("course__groups")
        .order_by("-updated_at", "-created_at")
    )

    return render(
        request,
        "role_admin/applications.html",
        {
            "applications": applications_list,
            "statuses": Application.ApplicationStatus.choices,
            "notice": notice,
            "error": error,
        },
    )


@admin_required
def schedule_board(request):
    notice = None
    error = None

    if request.method == "POST":
        try:
            if request.POST.get("action") == "toggle_visibility":
                schedule = get_object_or_404(Schedule, pk=request.POST.get("schedule_id"))
                schedule.is_visible_to_students = request.POST.get("is_visible_to_students") == "on"
                schedule.save(update_fields=["is_visible_to_students", "updated_at"])
                notice = "Доступность занятия для студентов обновлена."
                raise StopIteration

            group = get_object_or_404(StudyGroup, pk=request.POST.get("group"))
            lesson = None
            lesson_id = request.POST.get("lesson")
            if lesson_id:
                lesson = get_object_or_404(Lesson, pk=lesson_id, module__course=group.course)

            teacher = None
            teacher_id = request.POST.get("teacher")
            if teacher_id:
                teacher = get_object_or_404(Users, pk=teacher_id, role__name__iexact="teacher")

            start_at = parse_datetime_input(request.POST.get("start_at"))
            end_at = parse_datetime_input(request.POST.get("end_at"))
            if end_at <= start_at:
                raise ValidationError("Время окончания должно быть позже времени начала.")

            schedule = Schedule.objects.create(
                group=group,
                lesson=lesson,
                teacher=teacher or group.teacher,
                start_at=start_at,
                end_at=end_at,
                meeting_code=request.POST.get("meeting_code", "").strip(),
                is_visible_to_students=request.POST.get("is_visible_to_students") == "on",
                status=Schedule.ScheduleStatus.PLANNED,
            )
            if not schedule.meeting_code:
                schedule.meeting_code = f"AE-{schedule.id:04d}"
                schedule.save(update_fields=["meeting_code"])
            lesson_title = schedule.lesson.title if schedule.lesson else "занятие по курсу"
            notify_group_students(
                group,
                "Назначено занятие",
                f'По курсу "{group.course.title}" назначено занятие "{lesson_title}" на {timezone.localtime(schedule.start_at).strftime("%d.%m.%Y %H:%M")}.',
            )
            notice = "Занятие добавлено в расписание."
        except StopIteration:
            pass
        except ValidationError as exc:
            error = " ".join(exc.messages)

    schedules = (
        Schedule.objects
        .select_related("group", "group__course", "lesson", "teacher")
        .order_by("start_at")[:80]
    )
    groups = (
        StudyGroup.objects
        .select_related("course", "teacher")
        .filter(is_active=True)
        .order_by("course__title", "name")
    )
    lessons = (
        Lesson.objects
        .select_related("module", "module__course")
        .order_by("module__course__title", "module__sort_order", "sort_order")
    )

    return render(
        request,
        "role_admin/schedule.html",
        {
            "notice": notice,
            "error": error,
            "groups": groups,
            "teachers": get_teacher_queryset(),
            "lessons": lessons,
            "schedules": schedules,
            "now": timezone.now(),
        },
    )


@admin_required
def table_list(request):
    search_query = request.GET.get("q", "").strip()
    tables = get_table_meta()
    if search_query:
        lowered_query = search_query.casefold()
        tables = [
            table
            for table in tables
            if lowered_query in str(table["verbose_name"]).casefold()
            or lowered_query in table["db_table"].casefold()
        ]

    return render(
        request,
        "role_admin/table_list.html",
        {
            "database_name": get_database_name(),
            "tables": tables,
            "search_query": search_query,
        },
    )


@admin_required
def table_detail(request, model_name):
    model = get_model_or_404(model_name)
    fields = get_display_fields(model)
    objects = model.objects.all().order_by(model._meta.pk.name)
    search_query = request.GET.get("q", "").strip()
    selected_filters = {
        key: request.GET.get(key, "").strip()
        for key in FILTER_PARAM_NAMES
    }
    objects = search_objects(model._meta.model_name, objects, search_query)
    objects = apply_table_filters(model._meta.model_name, objects, selected_filters)
    table_filters = get_table_filters(model._meta.model_name, selected_filters)

    paginator = Paginator(objects, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "role_admin/table_detail.html",
        {
            "model": model,
            "model_name": model._meta.model_name,
            "model_verbose": model._meta.verbose_name_plural,
            "db_table": model._meta.db_table,
            "table_description": TABLE_DESCRIPTIONS.get(model._meta.model_name, "Системная таблица проекта."),
            "database_name": get_database_name(),
            "columns": [get_column_label(field) for field in fields],
            "rows": build_rows(page.object_list, fields),
            "page": page,
            "query_string": query_params.urlencode(),
            "search_query": search_query,
            "search_placeholder": SEARCH_PLACEHOLDERS.get(model._meta.model_name),
            "table_filters": table_filters,
            "has_table_tools": bool(search_query or table_filters or SEARCH_PLACEHOLDERS.get(model._meta.model_name)),
            "filters_collapsible": model._meta.model_name in COLLAPSIBLE_FILTER_TABLES,
            "notice": request.GET.get("notice"),
            "error": request.GET.get("error"),
        },
    )


@admin_required
def record_create(request, model_name):
    model = get_model_or_404(model_name)
    form_class = get_model_form_class(model)
    return_query = query_from_string(request.GET.urlencode() or request.POST.get("next_query", ""))

    if request.method == "POST":
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return table_redirect(model, base_query=return_query, notice="Запись добавлена.")
    else:
        form = form_class()

    return render(
        request,
        "role_admin/record_form.html",
        {
            "form": form,
            "model_name": model._meta.model_name,
            "model_verbose": model._meta.verbose_name_plural,
            "title": "Добавить запись",
            "return_query": return_query.urlencode(),
        },
    )


@admin_required
def record_update(request, model_name, pk):
    model = get_model_or_404(model_name)
    obj = get_object_or_404(model, pk=pk)
    form_class = get_model_form_class(model)
    return_query = query_from_string(request.GET.urlencode() or request.POST.get("next_query", ""))

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            return table_redirect(model, base_query=return_query, notice="Запись сохранена.")
    else:
        form = form_class(instance=obj)

    return render(
        request,
        "role_admin/record_form.html",
        {
            "form": form,
            "object": obj,
            "model_name": model._meta.model_name,
            "model_verbose": model._meta.verbose_name_plural,
            "title": "Изменить запись",
            "return_query": return_query.urlencode(),
        },
    )


@admin_required
def record_delete(request, model_name, pk):
    model = get_model_or_404(model_name)
    obj = get_object_or_404(model, pk=pk)
    return_query = query_from_string(request.GET.urlencode() or request.POST.get("next_query", ""))
    error = None

    if request.method == "POST":
        try:
            obj.delete()
            return table_redirect(model, base_query=return_query, notice="Запись удалена.")
        except ProtectedError:
            error = "Запись нельзя удалить, потому что на нее ссылаются другие таблицы."

    return render(
        request,
        "role_admin/confirm_delete.html",
        {
            "object": obj,
            "model_name": model._meta.model_name,
            "model_verbose": model._meta.verbose_name_plural,
            "error": error,
            "return_query": return_query.urlencode(),
        },
    )


@admin_required
def database_tools(request):
    return render(
        request,
        "role_admin/database.html",
        {
            "database_name": get_database_name(),
            "database_engine": get_database_engine(),
            "tables": get_table_meta(),
            "notice": request.GET.get("notice"),
            "error": request.GET.get("error"),
        },
    )


@admin_required
def export_database_json(request):
    objects = chain.from_iterable(
        model.objects.all().order_by(model._meta.pk.name)
        for model in get_managed_models()
    )
    payload = serializers.serialize("json", objects, indent=2)
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{get_database_name()}_backup.json"'
    return response


@admin_required
def export_table_json(request, model_name):
    model = get_model_or_404(model_name)
    payload = serializers.serialize(
        "json",
        model.objects.all().order_by(model._meta.pk.name),
        indent=2,
    )
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{model._meta.db_table}.json"'
    return response


@admin_required
def export_table_csv(request, model_name):
    model = get_model_or_404(model_name)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{model._meta.db_table}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    fields = model._meta.concrete_fields
    writer.writerow([field.attname for field in fields])
    for obj in model.objects.all().order_by(model._meta.pk.name):
        writer.writerow([field.value_from_object(obj) for field in fields])
    return response


@admin_required
def import_database_json(request):
    if request.method != "POST":
        return redirect("role_admin:database_tools")

    try:
        payload = get_uploaded_json(request)
        objects = deserialize_objects(payload)
        with transaction.atomic():
            if request.POST.get("replace") == "on":
                for model in reversed(get_managed_models()):
                    model.objects.all().delete()
            count = save_deserialized_objects(objects)
    except Exception as exc:
        return redirect_with_query(
            "role_admin:database_tools",
            query={"error": f"Не удалось загрузить файл: {exc}"},
        )

    return redirect_with_query(
        "role_admin:database_tools",
        query={"notice": f"Загружено записей: {count}."},
    )


@admin_required
def import_table_json(request, model_name):
    model = get_model_or_404(model_name)
    if request.method != "POST":
        return table_redirect(model)

    try:
        payload = get_uploaded_json(request)
        objects = deserialize_objects(payload, expected_model=model)
        with transaction.atomic():
            if request.POST.get("replace") == "on":
                model.objects.all().delete()
            count = save_deserialized_objects(objects)
    except Exception as exc:
        return table_redirect(model, error=f"Не удалось загрузить файл: {exc}")

    return table_redirect(model, notice=f"Загружено записей: {count}.")
