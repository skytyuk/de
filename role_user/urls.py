from django.urls import path

from . import views


app_name = "role_user"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("courses/", views.course_list, name="courses"),
    path("courses/<int:course_id>/", views.course_detail, name="course_detail"),
    path("courses/<int:course_id>/apply/", views.apply_course, name="apply_course"),
    path("my-courses/", views.my_courses, name="my_courses"),
    path("my-courses/<int:course_id>/", views.my_course_detail, name="my_course_detail"),
    path("my-courses/<int:course_id>/lessons/<int:schedule_id>/", views.lesson_detail, name="lesson_detail"),
    path("my-courses/<int:course_id>/lessons/<int:schedule_id>/tests/<int:test_id>/", views.test_detail, name="test_detail"),
    path("notifications/", views.notifications, name="notifications"),
]
