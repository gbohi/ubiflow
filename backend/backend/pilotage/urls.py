from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'perimetres-consultation', views.PerimetreConsultationViewSet, basename='perimetre-consultation')
urlpatterns = router.urls + [
    path('accueil/', views.AccueilView.as_view()),
    path('recherche/', views.RechercheView.as_view()),
    path('tableaux-de-bord/', views.ProfilsView.as_view()),
    path('tableaux-de-bord/<str:profil>/', views.TableauDeBordView.as_view()),
]
