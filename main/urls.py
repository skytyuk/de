from django.urls import path
from . import views

app_name = "main"

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("notification-counts/", views.notification_counts, name="notification_counts"),
    path("load-test/roles/", views.load_test_create_role, name="load_test_create_role"),
]
