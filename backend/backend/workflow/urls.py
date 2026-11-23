from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ChampsConditionView, DelegationViewSet, EtapeViewSet, TacheViewSet, VersionWorkflowViewSet

router = DefaultRouter()
router.register(r'versions-workflow', VersionWorkflowViewSet, basename='version-workflow')
router.register(r'etapes-workflow', EtapeViewSet, basename='etape-workflow')
router.register(r'taches', TacheViewSet, basename='tache')
router.register(r'delegations', DelegationViewSet, basename='delegation')
urlpatterns = [path('champs-condition/', ChampsConditionView.as_view(), name='champs-condition')] + router.urls
