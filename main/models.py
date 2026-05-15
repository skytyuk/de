from pathlib import Path
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.core.files.storage import default_storage
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


def validate_single_file_or_url(file_value, url_value, empty_message, both_message):
    has_file = bool(file_value)
    has_url = bool((url_value or "").strip())

    if has_file and has_url:
        raise ValidationError({
            "file": both_message,
            "file_url": both_message,
        })

    if not has_file and not has_url:
        raise ValidationError({
            "file": empty_message,
            "file_url": empty_message,
        })


def include_auto_update_field(kwargs, field_name):
    update_fields = kwargs.get("update_fields")
    if update_fields is not None:
        kwargs["update_fields"] = set(update_fields) | {field_name}

def user_image_path(instance, filename):
    extension = Path(filename).suffix.lower()
    directory = f'user_images/id_{instance.pk}'

    try:
        _, existing_files = default_storage.listdir(directory)
    except FileNotFoundError:
        existing_files = []

    existing_numbers = [
        int(Path(file_name).stem)
        for file_name in existing_files
        if Path(file_name).stem.isdigit()
    ]
    next_number = max(existing_numbers, default=0) + 1

    return f'{directory}/{next_number}{extension}'

# ============================================================
# РОЛИ
# Хранит роли пользователей: студент, преподаватель, администратор.
# ============================================================

class Roles(models.Model):
    name = models.CharField(unique=True, max_length=255)

    class Meta:
        db_table = 'roles'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name

# ============================================================
# ПОЛЬЗОВАТЕЛИ
# Хранит всех пользователей системы.
# ============================================================

class Users(models.Model):
    last_name = models.CharField(max_length=255)
    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True, max_length=255)
    password = models.CharField(max_length=255)
    phone = models.CharField(unique=True, max_length=20, blank=True, null=True)
    image = models.ImageField(upload_to=user_image_path, max_length=255, blank=True, null=True)
    role = models.ForeignKey(Roles, on_delete=models.RESTRICT, db_column='role_id', related_name='users')

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                name='users_email_lower_unique'
            )
        ]

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        image = self.image
        if self._state.adding and image:
            self.image = None
            super().save(*args, **kwargs)
            self.image = image
            second_save_kwargs = {"update_fields": ["image"]}
            if "using" in kwargs:
                second_save_kwargs["using"] = kwargs["using"]
            super().save(**second_save_kwargs)
            return

        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

# ============================================================
# КАТЕГОРИИ КУРСОВ
# Например: программирование, дизайн, языки.
# ============================================================

class CourseCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_categories'
        verbose_name = 'Course category'
        verbose_name_plural = 'Course categories'

    def __str__(self):
        return self.name


class CourseTag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_tags'
        verbose_name = 'Course tag'
        verbose_name_plural = 'Course tags'
        ordering = ['name']

    def __str__(self):
        return self.name


# ============================================================
# КУРСЫ
# Хранит основную информацию о курсе.
# ============================================================

class Course(models.Model):
    class CourseLevel(models.TextChoices):
        BEGINNER = 'beginner', 'Начальный'
        INTERMEDIATE = 'intermediate', 'Средний'
        ADVANCED = 'advanced', 'Продвинутый'
        MIXED = 'mixed', 'Смешанный'

    category = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        related_name='courses',
        blank=True,
        null=True
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    level = models.CharField(
        max_length=50,
        choices=CourseLevel.choices,
        default=CourseLevel.BEGINNER
    )
    for_whom_description = models.TextField('Описание для кого сделан курс', blank=True, null=True)
    tags = models.ManyToManyField(
        CourseTag,
        through='CourseTagRelation',
        related_name='courses',
        blank=True,
    )

    duration_hours = models.PositiveIntegerField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses'
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def __str__(self):
        return self.title


class CourseTagRelation(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='course_tag_relations'
    )
    tag = models.ForeignKey(
        CourseTag,
        on_delete=models.CASCADE,
        related_name='course_relations'
    )

    class Meta:
        db_table = 'course_tag_relations'
        verbose_name = 'Course tag relation'
        verbose_name_plural = 'Course tag relations'
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'tag'],
                name='unique_course_tag_relation'
            )
        ]

    def __str__(self):
        return f'{self.course} — {self.tag}'


# ============================================================
# ПРЕПОДАВАТЕЛИ КУРСОВ.
# Связывает курсы и преподавателей.
# ============================================================

class CourseTeacher(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='course_teachers'
    )

    teacher = models.ForeignKey(
        Users,
        on_delete=models.RESTRICT,
        related_name='teacher_courses'
    )

    class Meta:
        db_table = 'course_teachers'
        verbose_name = 'Course teacher'
        verbose_name_plural = 'Course teachers'
        constraints = [
            models.UniqueConstraint(
                fields=['course', 'teacher'],
                name='unique_course_teacher'
            )
        ]

    def __str__(self):
        return f'{self.course} — {self.teacher}'


# ============================================================
# УЧЕБНЫЕ ГРУППЫ
# Группа студентов на конкретном курсе.
# ============================================================

class StudyGroup(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='groups'
    )

    teacher = models.ForeignKey(
        Users,
        on_delete=models.RESTRICT,
        related_name='study_groups',
        blank=True,
        null=True
    )

    name = models.CharField(max_length=255)

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    max_students = models.PositiveIntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'study_groups'
        verbose_name = 'Study group'
        verbose_name_plural = 'Study groups'

    def __str__(self):
        return self.name


# ============================================================
# МОДУЛИ КУРСОВ
# Курс делится на модули.
# ============================================================

class CourseModule(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    sort_order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course_modules'
        verbose_name = 'Course module'
        verbose_name_plural = 'Course modules'
        ordering = ['sort_order']

    def __str__(self):
        return self.title


# ============================================================
# ЗАНЯТИЯ
# Уроки внутри модулей.
# ============================================================

class Lesson(models.Model):
    class LessonType(models.TextChoices):
        ONLINE = 'online', 'Онлайн-занятие'
        OFFLINE = 'offline', 'Оффлайн-занятие'

    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name='lessons'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    lesson_type = models.CharField(
        max_length=50,
        choices=LessonType.choices,
        default=LessonType.ONLINE
    )

    sort_order = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lessons'
        verbose_name = 'Lesson'
        verbose_name_plural = 'Lessons'
        ordering = ['sort_order']

    def __str__(self):
        return self.title


# ============================================================
# МАТЕРИАЛЫ.
# Материалы к занятию: файл, ссылка или видео.
# ============================================================

class Material(models.Model):
    class MaterialType(models.TextChoices):
        FILE = 'file', 'Файл'
        LINK = 'link', 'Ссылка'
        VIDEO = 'video', 'Видео'

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='materials'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    material_type = models.CharField(
        max_length=50,
        choices=MaterialType.choices,
        default=MaterialType.FILE
    )

    file = models.FileField(upload_to='materials/', blank=True, null=True)
    file_url = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'materials'
        verbose_name = 'Material'
        verbose_name_plural = 'Materials'

    def clean(self):
        super().clean()
        validate_single_file_or_url(
            self.file,
            self.file_url,
            "Добавьте файл или ссылку на материал.",
            "Заполните только одно поле: файл или ссылку.",
        )

    def __str__(self):
        return self.title


# ============================================================
# ЗАЯВКИ НА КУРСЫ
# Пользователь подает заявку на выбранный курс.
# ============================================================

class Application(models.Model):
    class ApplicationStatus(models.TextChoices):
        NEW = 'new', 'Новая'
        APPROVED = 'approved', 'Одобрена'
        REJECTED = 'rejected', 'Отклонена'
        CANCELLED = 'cancelled', 'Отменена'

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='applications'
    )

    status = models.CharField(
        max_length=50,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.NEW
    )

    comment = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'applications'
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_application'
            )
        ]

    def __str__(self):
        return f'{self.student} — {self.course}'


# ============================================================
# ИСТОРИЯ СТАТУСОВ ЗАЯВОК
# Показывает, кто и когда изменил статус заявки.
# ============================================================

class ApplicationStatusHistory(models.Model):
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='status_history'
    )

    changed_by = models.ForeignKey(
        Users,
        on_delete=models.SET_NULL,
        related_name='changed_applications',
        blank=True,
        null=True
    )

    old_status = models.CharField(
        max_length=50,
        choices=Application.ApplicationStatus.choices,
        blank=True,
        null=True
    )

    new_status = models.CharField(
        max_length=50,
        choices=Application.ApplicationStatus.choices
    )

    comment = models.TextField(blank=True, null=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'application_status_history'
        verbose_name = 'Application status history'
        verbose_name_plural = 'Application status histories'

    def __str__(self):
        return f'{self.application} → {self.new_status}'


# ============================================================
# ЗАЧИСЛЕНИЯ
# После одобрения заявки студент зачисляется на курс.
# ============================================================

class Enrollment(models.Model):
    class EnrollmentStatus(models.TextChoices):
        ACTIVE = 'active', 'Обучается'
        COMPLETED = 'completed', 'Завершил'
        EXPELLED = 'expelled', 'Отчислен'
        CANCELLED = 'cancelled', 'Отменено'

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.SET_NULL,
        related_name='enrollments',
        blank=True,
        null=True
    )

    application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        related_name='enrollments',
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=50,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE
    )

    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'enrollments'
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_enrollment'
            )
        ]

    def __str__(self):
        return f'{self.student} — {self.course}'

    def save(self, *args, **kwargs):
        if self.status != self.EnrollmentStatus.ACTIVE and not self.completed_at:
            self.completed_at = timezone.now()
            include_auto_update_field(kwargs, "completed_at")
        elif self.status == self.EnrollmentStatus.ACTIVE:
            self.completed_at = None
            include_auto_update_field(kwargs, "completed_at")
        super().save(*args, **kwargs)


# ============================================================
# ДОСТУПНОСТЬ ПРЕПОДАВАТЕЛЯ
# Нужно для составления расписания.
# ============================================================

class TeacherAvailability(models.Model):
    teacher = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='availability'
    )

    day_of_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)]
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = 'teacher_availability'
        verbose_name = 'Teacher availability'
        verbose_name_plural = 'Teacher availability'

    def __str__(self):
        return f'{self.teacher}: {self.day_of_week} {self.start_time}-{self.end_time}'


# ============================================================
# РАСПИСАНИЕ
# Хранит дату, время, группу, занятие и ссылку на онлайн-встречу.
# ============================================================

class Schedule(models.Model):
    class ScheduleStatus(models.TextChoices):
        PLANNED = 'planned', 'Запланировано'
        COMPLETED = 'completed', 'Проведено'
        CANCELLED = 'cancelled', 'Отменено'

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name='schedule_items'
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        related_name='schedule_items',
        blank=True,
        null=True
    )

    teacher = models.ForeignKey(
        Users,
        on_delete=models.RESTRICT,
        related_name='schedule_items',
        blank=True,
        null=True
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    meeting_code = models.CharField(max_length=80, blank=True, null=True)
    is_visible_to_students = models.BooleanField(default=False)

    status = models.CharField(
        max_length=50,
        choices=ScheduleStatus.choices,
        default=ScheduleStatus.PLANNED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule'
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedule'

    def __str__(self):
        return f'{self.group} — {self.start_at}'


# ============================================================
# ИСТОРИЯ ИЗМЕНЕНИЙ РАСПИСАНИЯ.
# Хранит переносы занятий.
# ============================================================

class ScheduleChange(models.Model):
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='changes'
    )

    changed_by = models.ForeignKey(
        Users,
        on_delete=models.SET_NULL,
        related_name='schedule_changes',
        blank=True,
        null=True
    )

    old_start_at = models.DateTimeField(blank=True, null=True)
    old_end_at = models.DateTimeField(blank=True, null=True)

    new_start_at = models.DateTimeField(blank=True, null=True)
    new_end_at = models.DateTimeField(blank=True, null=True)

    reason = models.TextField(blank=True, null=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'schedule_changes'
        verbose_name = 'Schedule change'
        verbose_name_plural = 'Schedule changes'

    def __str__(self):
        return f'Изменение {self.schedule}'


# ============================================================
# ПОСЕЩАЕМОСТЬ
# Фиксирует присутствие студента на онлайн-занятии.
# ============================================================

class LessonAttendance(models.Model):
    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', 'Присутствовал'
        ABSENT = 'absent', 'Отсутствовал'
        LATE = 'late', 'Опоздал'

    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name='attendance'
    )

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='attendance'
    )

    status = models.CharField(
        max_length=50,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.ABSENT
    )

    joined_at = models.DateTimeField(blank=True, null=True)
    left_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'lesson_attendance'
        verbose_name = 'Lesson attendance'
        verbose_name_plural = 'Lesson attendance'
        constraints = [
            models.UniqueConstraint(
                fields=['schedule', 'student'],
                name='unique_schedule_student_attendance'
            )
        ]

    def __str__(self):
        return f'{self.student} — {self.schedule}'


# ============================================================
# ЗАДАНИЯ
# Практические задания к занятиям.
# ============================================================

class Assignment(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='assignments'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    file_url = models.CharField(max_length=500, blank=True, null=True)

    max_score = models.PositiveIntegerField(default=100)
    deadline = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments'
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'

    def clean(self):
        super().clean()
        validate_single_file_or_url(
            self.file,
            self.file_url,
            "Добавьте файл или ссылку на задание.",
            "Заполните только одно поле: файл или ссылку.",
        )

    def __str__(self):
        return self.title


# ============================================================
# ОТВЕТЫ СТУДЕНТОВ НА ЗАДАНИЯ.
# Хранит ответ, файл, оценку и комментарий преподавателя.
# ============================================================

class StudentSubmission(models.Model):
    class SubmissionStatus(models.TextChoices):
        SUBMITTED = 'submitted', 'Отправлено'
        CHECKED = 'checked', 'Проверено'
        RETURNED = 'returned', 'Возвращено'

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='submissions'
    )

    answer_text = models.TextField(blank=True, null=True)
    file_url = models.CharField(max_length=500, blank=True, null=True)
    file = models.FileField(upload_to='submissions/', blank=True, null=True)

    score = models.PositiveIntegerField(blank=True, null=True)
    feedback = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=50,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'student_submissions'
        verbose_name = 'Student submission'
        verbose_name_plural = 'Student submissions'
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'student'],
                name='unique_assignment_student_submission'
            )
        ]

    def clean(self):
        super().clean()
        validate_single_file_or_url(
            self.file,
            self.file_url,
            "Добавьте файл или ссылку к ответу.",
            "Заполните только одно поле: файл или ссылку.",
        )

    def __str__(self):
        return f'{self.student} — {self.assignment}'

    def save(self, *args, **kwargs):
        if self.status == self.SubmissionStatus.CHECKED and not self.checked_at:
            self.checked_at = timezone.now()
            include_auto_update_field(kwargs, "checked_at")
        elif self.status != self.SubmissionStatus.CHECKED:
            self.checked_at = None
            include_auto_update_field(kwargs, "checked_at")
        super().save(*args, **kwargs)


# ============================================================
# ТЕСТЫ
# Тесты к занятиям.
# ============================================================

class Test(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='tests'
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    passing_score = models.PositiveIntegerField(default=70)
    max_attempts = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tests'
        verbose_name = 'Test'
        verbose_name_plural = 'Tests'

    def __str__(self):
        return self.title


# ============================================================
# ВОПРОСЫ ТЕСТОВ
# ============================================================

class TestQuestion(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE = 'single', 'Один ответ'
        MULTIPLE = 'multiple', 'Несколько ответов'
        TEXT = 'text', 'Текстовый ответ'

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='questions'
    )

    question_text = models.TextField()

    question_type = models.CharField(
        max_length=50,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE
    )

    score = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'test_questions'
        verbose_name = 'Test question'
        verbose_name_plural = 'Test questions'
        ordering = ['sort_order']

    def __str__(self):
        return self.question_text[:50]


# ============================================================
# ВАРИАНТЫ ОТВЕТОВ НА ВОПРОСЫ
# ============================================================

class TestAnswer(models.Model):
    question = models.ForeignKey(
        TestQuestion,
        on_delete=models.CASCADE,
        related_name='answers'
    )

    answer_text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'test_answers'
        verbose_name = 'Test answer'
        verbose_name_plural = 'Test answers'

    def __str__(self):
        return self.answer_text[:50]


# ============================================================
# ПОПЫТКИ ПРОХОЖДЕНИЯ ТЕСТОВ
# ============================================================

class TestAttempt(models.Model):
    class AttemptStatus(models.TextChoices):
        STARTED = 'started', 'Начат'
        PASSED = 'passed', 'Пройден'
        FAILED = 'failed', 'Не пройден'

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='attempts'
    )

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='test_attempts'
    )

    score = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=50,
        choices=AttemptStatus.choices,
        default=AttemptStatus.STARTED
    )

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'test_attempts'
        verbose_name = 'Test attempt'
        verbose_name_plural = 'Test attempts'

    def __str__(self):
        return f'{self.student} — {self.test}'

    def save(self, *args, **kwargs):
        if self.status == self.AttemptStatus.PASSED and not self.finished_at:
            self.finished_at = timezone.now()
            include_auto_update_field(kwargs, "finished_at")
        elif self.status == self.AttemptStatus.STARTED:
            self.finished_at = None
            include_auto_update_field(kwargs, "finished_at")
        super().save(*args, **kwargs)


# ============================================================
# ОТВЕТЫ СТУДЕНТОВ В ТЕСТАХ
# ============================================================

class StudentTestAnswer(models.Model):
    attempt = models.ForeignKey(
        TestAttempt,
        on_delete=models.CASCADE,
        related_name='student_answers'
    )

    question = models.ForeignKey(
        TestQuestion,
        on_delete=models.CASCADE,
        related_name='student_answers'
    )

    answer = models.ForeignKey(
        TestAnswer,
        on_delete=models.SET_NULL,
        related_name='student_answers',
        blank=True,
        null=True
    )

    text_answer = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'student_test_answers'
        verbose_name = 'Student test answer'
        verbose_name_plural = 'Student test answers'

    def __str__(self):
        return f'{self.attempt} — {self.question}'


# ============================================================
# ПРОГРЕСС ПО ЗАНЯТИЯМ
# Показывает, начал студент урок или завершил его.
# ============================================================

class LessonProgress(models.Model):
    class ProgressStatus(models.TextChoices):
        NOT_STARTED = 'not_started', 'Не начато'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Завершено'

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='lesson_progress'
    )

    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='progress'
    )

    status = models.CharField(
        max_length=50,
        choices=ProgressStatus.choices,
        default=ProgressStatus.NOT_STARTED
    )

    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'lesson_progress'
        verbose_name = 'Lesson progress'
        verbose_name_plural = 'Lesson progress'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'lesson'],
                name='unique_student_lesson_progress'
            )
        ]

    def __str__(self):
        return f'{self.student} — {self.lesson}'

    def save(self, *args, **kwargs):
        if self.status == self.ProgressStatus.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
            include_auto_update_field(kwargs, "completed_at")
        elif self.status != self.ProgressStatus.COMPLETED:
            self.completed_at = None
            include_auto_update_field(kwargs, "completed_at")
        super().save(*args, **kwargs)


# ============================================================
# КОММЕНТАРИИ К ЗАНЯТИЯМ
# Нужны для вопросов студентов и ответов преподавателя.
# ============================================================

class LessonComment(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='lesson_comments'
    )

    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lesson_comments'
        verbose_name = 'Lesson comment'
        verbose_name_plural = 'Lesson comments'

    def __str__(self):
        return self.text[:50]


# ============================================================
# ОПЛАТЫ
# Хранит оплату за курсы.
# ============================================================

class Payment(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачено'
        FAILED = 'failed', 'Ошибка'
        REFUNDED = 'refunded', 'Возврат'

    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=50,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )

    payment_method = models.CharField(max_length=100, blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f'{self.student} — {self.amount}'


# ============================================================
# СЕРТИФИКАТЫ
# Сертификат выдается после завершения курса.
# ============================================================

class Certificate(models.Model):
    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='certificates'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='certificates'
    )

    certificate_number = models.CharField(max_length=100, unique=True)
    file = models.FileField(upload_to='certificates/', blank=True, null=True)

    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'certificates'
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_certificate'
            )
        ]

    def __str__(self):
        return self.certificate_number


# ============================================================
# УВЕДОМЛЕНИЯ
# Уведомления для пользователей.
# ============================================================

class Notification(models.Model):
    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return self.title


# ============================================================
# ОТЗЫВЫ О КУРСАХ
# Студент может поставить оценку и написать отзыв.
# ============================================================

class CourseReview(models.Model):
    student = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='course_reviews'
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    comment = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_reviews'
        verbose_name = 'Course review'
        verbose_name_plural = 'Course reviews'
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='unique_student_course_review'
            )
        ]

    def __str__(self):
        return f'{self.course} — {self.rating}'


# ============================================================
# ОБРАЩЕНИЯ В ПОДДЕРЖКУ
# Пользователь может создать обращение.
# ============================================================

class SupportTicket(models.Model):
    class TicketStatus(models.TextChoices):
        OPEN = 'open', 'Открыто'
        IN_PROGRESS = 'in_progress', 'В работе'
        CLOSED = 'closed', 'Закрыто'

    user = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='support_tickets'
    )

    subject = models.CharField(max_length=255)

    status = models.CharField(
        max_length=50,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN
    )

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'support_tickets'
        verbose_name = 'Support ticket'
        verbose_name_plural = 'Support tickets'

    def __str__(self):
        return self.subject

    def save(self, *args, **kwargs):
        if self.status == self.TicketStatus.CLOSED and not self.closed_at:
            self.closed_at = timezone.now()
            include_auto_update_field(kwargs, "closed_at")
        elif self.status != self.TicketStatus.CLOSED:
            self.closed_at = None
            include_auto_update_field(kwargs, "closed_at")
        super().save(*args, **kwargs)


# ============================================================
# СООБЩЕНИЯ В ПОДДЕРЖКЕ
# Переписка внутри обращения.
# ============================================================

class SupportMessage(models.Model):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    sender = models.ForeignKey(
        Users,
        on_delete=models.CASCADE,
        related_name='support_messages'
    )

    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'support_messages'
        verbose_name = 'Support message'
        verbose_name_plural = 'Support messages'

    def __str__(self):
        return self.message[:50]
