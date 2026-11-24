from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'pays', views.PaysViewSet, basename='pays')
router.register(r'villes', views.VilleViewSet, basename='ville')
router.register(r'distances', views.DistanceViewSet, basename='distance')
urlpatterns = [path('missions/calculer/', views.CalculerMissionView.as_view()),
               path('missions/clotures/', views.CloturesAControlerView.as_view())] + router.urls
