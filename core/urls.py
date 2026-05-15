from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('user/', include('role_user.urls')),
    path('role-admin/', include('role_admin.urls')),
    path('teacher/', include('role_teacher.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
