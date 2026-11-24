from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'baremes/per-diem', views.PerDiemViewSet, basename='per-diem')
router.register(r'baremes/kilometrique', views.TarifKilometriqueViewSet, basename='tarif-km')
router.register(r'baremes/transport-ville', views.TarifTransportVilleViewSet, basename='tarif-ville')
router.register(r'baremes/forfait-hors-pays', views.ForfaitTransportHorsPaysViewSet, basename='forfait-hors-pays')
router.register(r'baremes/taux-change', views.TauxChangeViewSet, basename='taux-change')
router.register(r'jours-feries', views.JourFerieViewSet, basename='jour-ferie')
urlpatterns = [path('parametres-systeme/', views.ParametreSystemeView.as_view())] + router.urls
