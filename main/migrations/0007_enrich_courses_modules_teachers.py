from django.contrib.auth.hashers import make_password
from django.db import migrations


TEACHERS = [
    {
        "email": "anna.smirnova.teacher@example.com",
        "phone": "+79992000001",
        "last_name": "Смирнова",
        "first_name": "Анна",
        "middle_name": "Игоревна",
    },
    {
        "email": "dmitry.orlov.teacher@example.com",
        "phone": "+79992000002",
        "last_name": "Орлов",
        "first_name": "Дмитрий",
        "middle_name": "Сергеевич",
    },
    {
        "email": "maria.kuznetsova.teacher@example.com",
        "phone": "+79992000003",
        "last_name": "Кузнецова",
        "first_name": "Мария",
        "middle_name": "Андреевна",
    },
    {
        "email": "alexey.volkov.teacher@example.com",
        "phone": "+79992000004",
        "last_name": "Волков",
        "first_name": "Алексей",
        "middle_name": "Павлович",
    },
    {
        "email": "elena.petrova.teacher@example.com",
        "phone": "+79992000005",
        "last_name": "Петрова",
        "first_name": "Елена",
        "middle_name": "Викторовна",
    },
]


COURSE_DETAILS = {
    "Python с нуля": {
        "level": "beginner",
        "target_audience": "Для новичков, которые хотят начать программировать без опыта.",
        "tags": "python, программирование, backend, основы",
        "teachers": ["anna.smirnova.teacher@example.com"],
        "modules": [
            "Основы синтаксиса Python",
            "Функции и структуры данных",
            "Работа с файлами и исключениями",
            "Итоговый мини-проект",
        ],
    },
    "Веб-разработка на Django": {
        "level": "intermediate",
        "target_audience": "Для тех, кто знает основы Python и хочет создавать веб-приложения.",
        "tags": "django, python, web, backend",
        "teachers": ["anna.smirnova.teacher@example.com", "dmitry.orlov.teacher@example.com"],
        "modules": [
            "Архитектура Django-проекта",
            "Модели, миграции и админка",
            "Шаблоны, формы и авторизация",
            "Публикация и поддержка проекта",
        ],
    },
    "Основы JavaScript": {
        "level": "beginner",
        "target_audience": "Для начинающих фронтенд-разработчиков и верстальщиков.",
        "tags": "javascript, frontend, dom, web",
        "teachers": ["dmitry.orlov.teacher@example.com"],
        "modules": [
            "Синтаксис и типы данных",
            "Функции, массивы и объекты",
            "DOM, события и формы",
            "Интерактивный проект",
        ],
    },
    "UI/UX дизайн интерфейсов": {
        "level": "intermediate",
        "target_audience": "Для дизайнеров и разработчиков, которые проектируют удобные интерфейсы.",
        "tags": "ui, ux, figma, интерфейсы",
        "teachers": ["maria.kuznetsova.teacher@example.com"],
        "modules": [
            "Исследование пользователей",
            "Информационная архитектура",
            "Компоненты и дизайн-система",
            "Прототипирование и тестирование",
        ],
    },
    "Графический дизайн": {
        "level": "beginner",
        "target_audience": "Для новичков, которые хотят освоить визуальную коммуникацию.",
        "tags": "дизайн, графика, композиция, типографика",
        "teachers": ["maria.kuznetsova.teacher@example.com"],
        "modules": [
            "Композиция и сетки",
            "Цвет и типографика",
            "Работа с макетами",
            "Подготовка портфолио",
        ],
    },
    "Английский для IT": {
        "level": "mixed",
        "target_audience": "Для студентов и специалистов IT, которым нужен технический английский.",
        "tags": "английский, it, коммуникация, документация",
        "teachers": ["alexey.volkov.teacher@example.com"],
        "modules": [
            "Техническая лексика",
            "Чтение документации",
            "Деловая переписка",
            "Собеседование на английском",
        ],
    },
    "Проектный менеджмент": {
        "level": "intermediate",
        "target_audience": "Для будущих руководителей проектов, тимлидов и координаторов команд.",
        "tags": "менеджмент, проекты, команда, planning",
        "teachers": ["alexey.volkov.teacher@example.com"],
        "modules": [
            "Жизненный цикл проекта",
            "Планирование задач и сроков",
            "Риски и коммуникации",
            "Защита проектного плана",
        ],
    },
    "Excel и аналитика данных": {
        "level": "beginner",
        "target_audience": "Для тех, кто работает с таблицами, отчетами и базовой аналитикой.",
        "tags": "excel, аналитика, данные, отчеты",
        "teachers": ["elena.petrova.teacher@example.com"],
        "modules": [
            "Формулы и функции",
            "Сводные таблицы",
            "Диаграммы и визуализация",
            "Итоговый аналитический отчет",
        ],
    },
    "Базы данных SQL": {
        "level": "intermediate",
        "target_audience": "Для начинающих разработчиков и аналитиков, которым нужны SQL-запросы.",
        "tags": "sql, базы данных, postgres, аналитика",
        "teachers": ["anna.smirnova.teacher@example.com", "elena.petrova.teacher@example.com"],
        "modules": [
            "Проектирование таблиц",
            "SELECT, JOIN и фильтрация",
            "Группировка и подзапросы",
            "Оптимизация и практика",
        ],
    },
    "SMM и продвижение": {
        "level": "beginner",
        "target_audience": "Для начинающих маркетологов, предпринимателей и контент-специалистов.",
        "tags": "smm, маркетинг, контент, реклама",
        "teachers": ["maria.kuznetsova.teacher@example.com"],
        "modules": [
            "Стратегия продвижения",
            "Контент-план и визуал",
            "Реклама и аналитика",
            "Итоговая кампания",
        ],
    },
}


def enrich_courses(apps, schema_editor):
    Roles = apps.get_model("main", "Roles")
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    CourseModule = apps.get_model("main", "CourseModule")
    CourseTeacher = apps.get_model("main", "CourseTeacher")

    teacher_role, _ = Roles.objects.get_or_create(name="teacher")
    teacher_by_email = {}

    for teacher_data in TEACHERS:
        teacher, created = Users.objects.get_or_create(
            email=teacher_data["email"],
            defaults={
                "last_name": teacher_data["last_name"],
                "first_name": teacher_data["first_name"],
                "middle_name": teacher_data["middle_name"],
                "phone": teacher_data["phone"],
                "password": make_password("Teacher123!"),
                "role": teacher_role,
            },
        )
        if not created:
            teacher.role = teacher_role
            teacher.save(update_fields=["role"])
        teacher_by_email[teacher.email] = teacher

    for title, details in COURSE_DETAILS.items():
        course = Course.objects.filter(title=title).first()
        if not course:
            continue

        course.level = details["level"]
        course.target_audience = details["target_audience"]
        course.tags = details["tags"]
        course.save(update_fields=["level", "target_audience", "tags", "updated_at"])

        for index, module_title in enumerate(details["modules"], start=1):
            CourseModule.objects.get_or_create(
                course=course,
                title=module_title,
                defaults={
                    "description": f"Модуль {index} курса {course.title}.",
                    "sort_order": index,
                },
            )

        for teacher_email in details["teachers"]:
            teacher = teacher_by_email.get(teacher_email)
            if teacher:
                CourseTeacher.objects.get_or_create(course=course, teacher=teacher)


def rollback_enriched_courses(apps, schema_editor):
    Users = apps.get_model("main", "Users")
    Course = apps.get_model("main", "Course")
    CourseModule = apps.get_model("main", "CourseModule")
    CourseTeacher = apps.get_model("main", "CourseTeacher")

    for title, details in COURSE_DETAILS.items():
        course = Course.objects.filter(title=title).first()
        if not course:
            continue

        CourseTeacher.objects.filter(course=course).delete()
        CourseModule.objects.filter(course=course, title__in=details["modules"]).delete()
        course.level = "beginner"
        course.target_audience = None
        course.tags = None
        course.save(update_fields=["level", "target_audience", "tags", "updated_at"])

    Users.objects.filter(email__in=[teacher["email"] for teacher in TEACHERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0006_course_level_course_tags_course_target_audience"),
    ]

    operations = [
        migrations.RunPython(enrich_courses, rollback_enriched_courses),
    ]
