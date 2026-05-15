from django.contrib import admin
from django import forms

from .models import (
    Application,
    ApplicationStatusHistory,
    Assignment,
    Certificate,
    Course,
    CourseCategory,
    CourseModule,
    CourseReview,
    CourseTag,
    CourseTagRelation,
    CourseTeacher,
    Enrollment,
    Lesson,
    LessonAttendance,
    LessonComment,
    LessonProgress,
    Material,
    Notification,
    Payment,
    Roles,
    Schedule,
    ScheduleChange,
    StudentSubmission,
    StudentTestAnswer,
    StudyGroup,
    SupportMessage,
    SupportTicket,
    TeacherAvailability,
    Test,
    TestAnswer,
    TestAttempt,
    TestQuestion,
    Users,
)


class UsersAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text="Оставьте пустым, чтобы не менять пароль"
    )

    class Meta:
        model = Users
        fields = '__all__'

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        elif user.pk:
            user.password = Users.objects.get(pk=user.pk).password
        if commit:
            user.save()
        return user


@admin.register(Roles)
class RolesAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'middle_name', 'email', 'password', 'phone', 'image', 'role_info')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    list_filter = ('role',)

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            kwargs['form'] = UsersAdminForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.set_password(obj.password)
        super().save_model(request, obj, form, change)

    def role_info(self, obj):
        if obj.role:
            return f"id{obj.role.id}_{obj.role.name}"
        return "-"

    role_info.short_description = 'Role'


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('name',)


@admin.register(CourseTag)
class CourseTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    search_fields = ('id', 'name')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'level', 'duration_hours', 'price', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'category', 'level', 'tags')
    search_fields = ('id', 'title', 'description', 'for_whom_description', 'tags__name')


@admin.register(CourseTagRelation)
class CourseTagRelationAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'tag')
    list_filter = ('course', 'tag')
    search_fields = ('course__title', 'tag__name')


@admin.register(CourseTeacher)
class CourseTeacherAdmin(admin.ModelAdmin):
    list_display = ('id', 'course', 'teacher')
    list_filter = ('course',)
    search_fields = ('course__title', 'teacher__first_name', 'teacher__last_name', 'teacher__email')


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'course', 'teacher', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active', 'course')
    search_fields = ('name', 'course__title', 'teacher__first_name', 'teacher__last_name')


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'course', 'sort_order')
    list_filter = ('course',)
    search_fields = ('title', 'course__title')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'module', 'sort_order')
    list_filter = ('module__course',)
    search_fields = ('title', 'module__title', 'module__course__title')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'lesson', 'created_at')
    list_filter = ('lesson__module__course',)
    search_fields = ('title', 'lesson__title')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'course', 'status', 'created_at', 'updated_at')
    list_editable = ('status',)
    list_filter = ('status', 'course')
    search_fields = ('student__first_name', 'student__last_name', 'student__email', 'course__title')


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'application', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status',)
    search_fields = ('application__student__email', 'application__course__title')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'course', 'group', 'status', 'enrolled_at')
    list_editable = ('group', 'status')
    list_filter = ('status', 'course', 'group')
    search_fields = ('student__first_name', 'student__last_name', 'student__email', 'course__title')


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'lesson', 'teacher', 'start_at', 'end_at', 'status')
    list_filter = ('status', 'group__course')
    search_fields = ('group__name', 'lesson__title', 'teacher__first_name', 'teacher__last_name')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'is_read', 'created_at')
    list_editable = ('is_read',)
    list_filter = ('is_read',)
    search_fields = ('user__email', 'title', 'message')


admin.site.register(TeacherAvailability)
admin.site.register(ScheduleChange)
admin.site.register(LessonAttendance)
admin.site.register(Assignment)
admin.site.register(StudentSubmission)
admin.site.register(Test)
admin.site.register(TestQuestion)
admin.site.register(TestAnswer)
admin.site.register(TestAttempt)
admin.site.register(StudentTestAnswer)
admin.site.register(LessonProgress)
admin.site.register(LessonComment)
admin.site.register(Payment)
admin.site.register(Certificate)
admin.site.register(CourseReview)
admin.site.register(SupportTicket)
admin.site.register(SupportMessage)
