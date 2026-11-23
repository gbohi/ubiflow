from rest_framework.routers import DefaultRouter

from .views import ChampTypeViewSet, DemandeViewSet, ExigencePieceViewSet, TypeDemandeViewSet, TypePieceViewSet

router = DefaultRouter()
router.register(r'types-demande', TypeDemandeViewSet, basename='type-demande')
router.register(r'champs-type', ChampTypeViewSet, basename='champ-type')
router.register(r'exigences-pieces', ExigencePieceViewSet, basename='exigence-piece')
router.register(r'types-pieces', TypePieceViewSet, basename='type-piece')
router.register(r'demandes', DemandeViewSet, basename='demande')
urlpatterns = router.urls
