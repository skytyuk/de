from django.db import migrations


COURSES = [
    {
        "category": "Программирование",
        "title": "Python с нуля",
        "description": "Базовый курс по Python, синтаксису, функциям и работе с файлами.",
        "duration_hours": 36,
        "price": 12000,
    },
    {
        "category": "Программирование",
        "title": "Веб-разработка на Django",
        "description": "Создание сайтов на Django: модели, маршруты, шаблоны и формы.",
        "duration_hours": 48,
        "price": 18000,
    },
    {
        "category": "Программирование",
        "title": "Основы JavaScript",
        "description": "Интерактивные страницы, работа с DOM, события и валидация форм.",
        "duration_hours": 34,
        "price": 11500,
    },
    {
        "category": "Дизайн",
        "title": "UI/UX дизайн интерфейсов",
        "description": "Проектирование экранов, сетки, компоненты и пользовательские сценарии.",
        "duration_hours": 40,
        "price": 15000,
    },
    {
        "category": "Дизайн",
        "title": "Графический дизайн",
        "description": "Композиция, типографика, цвет и подготовка макетов.",
        "duration_hours": 32,
        "price": 10500,
    },
    {
        "category": "Языки",
        "title": "Английский для IT",
        "description": "Профессиональная лексика, переписка, собеседования и документация.",
        "duration_hours": 30,
        "price": 9000,
    },
    {
        "category": "Бизнес",
        "title": "Проектный менеджмент",
        "description": "Планирование задач, работа с командой, риски и сроки проекта.",
        "duration_hours": 28,
        "price": 9800,
    },
    {
        "category": "Аналитика",
        "title": "Excel и аналитика данных",
        "description": "Формулы, сводные таблицы, диаграммы и базовый анализ данных.",
        "duration_hours": 24,
        "price": 7500,
    },
    {
        "category": "Программирование",
        "title": "Базы данных SQL",
        "description": "Таблицы, связи, SELECT-запросы, JOIN и основы проектирования БД.",
        "duration_hours": 30,
        "price": 11000,
    },
    {
        "category": "Маркетинг",
        "title": "SMM и продвижение",
        "description": "Контент-план, аналитика социальных сетей и запуск рекламных кампаний.",
        "duration_hours": 26,
        "price": 8500,
    },
]


def create_initial_courses(apps, schema_editor):
    CourseCategory = apps.get_model("main", "CourseCategory")
    Course = apps.get_model("main", "Course")

    categories = {}
    for course_data in COURSES:
        category_name = course_data["category"]
        categories[category_name], _ = CourseCategory.objects.get_or_create(
            name=category_name,
            defaults={"description": f"Курсы в направлении {category_name}."},
        )

    for course_data in COURSES:
        Course.objects.get_or_create(
            title=course_data["title"],
            defaults={
                "category": categories[course_data["category"]],
                "description": course_data["description"],
                "duration_hours": course_data["duration_hours"],
                "price": course_data["price"],
                "is_active": True,
            },
        )


def delete_initial_courses(apps, schema_editor):
    Course = apps.get_model("main", "Course")
    Course.objects.filter(title__in=[course["title"] for course in COURSES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0004_course_coursecategory_application_and_more"),
    ]

    operations = [
        migrations.RunPython(create_initial_courses, delete_initial_courses),
    ]
