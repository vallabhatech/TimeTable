from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/timetable/', include('timetable.urls')),
    path('__debug__/', include('debug_toolbar.urls')),
]