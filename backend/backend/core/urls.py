from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    # Lot 2 : demandes, moteur de workflow, notifications, journal (même préfixe /api/api/)
    path('api/api/', include('demandes.urls')),
    path('api/api/', include('workflow.urls')),
    path('api/api/', include('notifications.urls')),
    path('api/api/', include('audit.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)