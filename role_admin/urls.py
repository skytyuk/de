from django.urls import path

from . import views


app_name = "role_admin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("education/", views.education_overview, name="education"),
    path("applications/", views.applications, name="applications"),
    path("schedule/", views.schedule_board, name="schedule"),
    path("tables/", views.table_list, name="table_list"),
    path("tables/<slug:model_name>/", views.table_detail, name="table_detail"),
    path("tables/<slug:model_name>/add/", views.record_create, name="record_create"),
    path("tables/<slug:model_name>/<int:pk>/edit/", views.record_update, name="record_update"),
    path("tables/<slug:model_name>/<int:pk>/delete/", views.record_delete, name="record_delete"),
    path("database/", views.database_tools, name="database_tools"),
    path("export/database.json", views.export_database_json, name="export_database_json"),
    path("export/<slug:model_name>.json", views.export_table_json, name="export_table_json"),
    path("export/<slug:model_name>.csv", views.export_table_csv, name="export_table_csv"),
    path("import/database/", views.import_database_json, name="import_database_json"),
    path("import/<slug:model_name>/", views.import_table_json, name="import_table_json"),
]
