from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import *


class ConnexionSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        'no_active_account': 'Matricule ou mot de passe incorrect, ou compte désactivé.',
    }


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Connexion JWT avec limitation de débit (anti force brute)."""
    serializer_class = ConnexionSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class ThrottledTokenRefreshView(TokenRefreshView):
    """Renouvellement du jeton, lui aussi limité."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'token_refresh'


router = DefaultRouter()
# Utilisateurs, rôles et affectations
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'user-agences', UserAgenceViewSet)
router.register(r'user-services', UserServiceViewSet)
router.register(r'user-postes', UserPosteViewSet)
router.register(r'user-categoriesalaries', UserCategoriesalarieViewSet)
# Paramètres
router.register(r'agences', AgenceViewSet)
router.register(r'services', ServiceViewSet)          # Départements
router.register(r'postes', PosteViewSet)
router.register(r'fonctions', FonctionViewSet)
router.register(r'categoriesalaries', CategoriesalarieViewSet)
router.register(r'statuts', StatutViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
    # Listes complètes non paginées (listes déroulantes)
    path('api/allnopagin/agences/', AllAgenceNopginListAPIView.as_view(), name='allnopagin-agence-list'),
    path('api/allnopagin/statuts/', PublicStatutListAPIView.as_view(), name='allnopagin-statut-list'),
    path('api/allnopagin/fonctions/', FonctionListAPIView.as_view(), name='allnopagin-fonction-list'),
    path('api/allnopagin/services/', ServiceListAPIView.as_view(), name='allnopagin-service-list'),
    path('api/allnopagin/categoriesalaries/', CategoriesalarieListAPIView.as_view(),
         name='allnopagin-categoriesalarie-list'),
    path('api/allnopagin/postes/', PosteListAPIView.as_view(), name='allnopagin-poste-list'),
    path('api/allnopagin/groups/', GroupListAPIView.as_view(), name='allnopagin-group-list'),
    path('api/allnopagin/users/', AllUserNopginListAPIView.as_view(), name='allnopagin-user-list'),
]
