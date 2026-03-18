from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from decouple import config

ADMIN_URL = config('ADMIN_URL', default='secret-admin')

urlpatterns = [
    path(f'{ADMIN_URL}/', admin.site.urls),
    path('', include('core.urls')),
    path('flights/', include('flights.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)