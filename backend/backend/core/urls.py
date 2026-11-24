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
    # Lot 3 : barèmes, lieux, calcul des missions
    path('api/api/', include('baremes.urls')),
    path('api/api/', include('missions.urls')),
    # Lot 4 : trésorerie
    path('api/api/', include('tresorerie.urls')),
    # Lot 6 : tableaux de bord
    path('api/api/', include('pilotage.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)