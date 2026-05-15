from django.urls import path

from . import views


app_name = "role_teacher"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("groups/", views.groups, name="groups"),
    path("groups/<int:group_id>/", views.group_detail, name="group_detail"),
    path("schedule/", views.schedule, name="schedule"),
    path("submissions/", views.submissions, name="submissions"),
    path("content/", views.content, name="content"),
    path("notifications/", views.notifications, name="notifications"),
]
