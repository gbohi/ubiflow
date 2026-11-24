import hmac
import math
import logging
import secrets
from io import BytesIO

import django_filters
import requests
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import *
from .serializers import *
from .serializers import validate_password_custom
from .permissions import (
    IsAdminRole, IsGestionnaireRole, IsAuthenticated,
    ReadAuthenticatedWriteAdmin, ReadGestionnaireWriteAdmin,
    is_admin, is_super_admin,
    ADMIN_ROLES, ROLE_SUPER_ADMIN, LIBELLES_ROLES,
)

logger = logging.getLogger(__name__)


# ============================================================
# BASE VIEWSET — hérité par tous les autres ViewSets
# ============================================================

_NOMS_LIES = {
    'User': 'des utilisateurs', 'UserAgence': 'des affectations d\'agence',
    'UserService': 'des affectations de département', 'UserPoste': 'des postes d\'agents',
    'UserCategoriesalarie': 'des catégories d\'agents', 'Poste': 'des postes',
    'Service': 'des sous-départements', 'AffectationResponsabilite': 'des titulaires de responsabilité',
    'AffectationHierarchique': 'des affectations hiérarchiques', 'SituationVehicule': 'des situations de véhicule',
}


def refuser_si_utilise(instance, champ_libelle=None):
    """
    Refuse la suppression d'une ligne de référentiel encore utilisée : la
    base supprimerait en cascade tout ce qui y est rattaché.
    """
    from django.db.models.deletion import Collector, ProtectedError, RestrictedError
    nom = getattr(instance, champ_libelle, None) if champ_libelle else None
    nom = f"« {nom} »" if nom else "Cet élément"
    collecteur = Collector(using=instance._state.db or 'default')
    try:
        collecteur.collect([instance])
    except (ProtectedError, RestrictedError):
        raise ValidationError(f"{nom} est utilisé : il ne peut pas être supprimé.")
    lies = {m for m, objets in collecteur.data.items() if m is not type(instance) and objets}
    lies |= {qs.model for qs in collecteur.fast_deletes if qs.exists()}
    lies = {m for m in lies if not m._meta.auto_created}
    if lies:
        libelles = sorted({_NOMS_LIES.get(m.__name__, str(m._meta.verbose_name_plural)) for m in lies})
        raise ValidationError(
            f"{nom} est utilisé par {', '.join(libelles)} : il ne peut pas être supprimé.")


class BaseViewSet(viewsets.ModelViewSet):
    """
    Par défaut : lecture pour tout utilisateur connecté, écriture réservée
    aux administrateurs. Les ViewSets surchargent permission_classes si
    une autre règle s'applique.
    """
    permission_classes = [ReadAuthenticatedWriteAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Droits de la suppression multiple (administrateurs par défaut)
    bulk_delete_permission_classes = [IsAdminRole]
    # Référentiels : une ligne encore utilisée ne peut pas être supprimée
    # (la suppression effacerait en cascade utilisateurs, menus, commandes…)
    proteger_references = False
    # Champ libellé : deux lignes ne peuvent pas porter le même (casse ignorée)
    champ_libelle = None

    def get_permissions(self):
        if self.action == 'bulk_delete':
            return [p() for p in self.bulk_delete_permission_classes]
        return super().get_permissions()

    def verifier_suppression(self, instance):
        """Lève une ValidationError si `instance` ne doit pas être supprimée."""
        if self.proteger_references:
            refuser_si_utilise(instance, self.champ_libelle)

    def perform_destroy(self, instance):
        self.verifier_suppression(instance)
        instance.delete()

    def _verifier_libelle(self, serializer):
        champ = self.champ_libelle
        if not champ or champ not in serializer.validated_data:
            return
        valeur = (serializer.validated_data[champ] or '').strip()
        if not valeur:
            raise ValidationError("Le libellé est obligatoire.")
        serializer.validated_data[champ] = valeur
        doublons = serializer.Meta.model.objects.filter(**{f'{champ}__iexact': valeur})
        if serializer.instance is not None:
            doublons = doublons.exclude(pk=serializer.instance.pk)
        if doublons.exists():
            raise ValidationError(f"« {valeur} » existe déjà.")

    def perform_create(self, serializer):
        self._verifier_libelle(serializer)
        # Les champs d'audit viennent toujours de l'utilisateur connecté
        serializer.validated_data.pop('user_created', None)
        serializer.save(
            user_created=self.request.user,
            user_updated=self.request.user
        )

    def perform_update(self, serializer):
        self._verifier_libelle(serializer)
        serializer.validated_data.pop('user_created', None)
        serializer.save(user_updated=self.request.user)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])

        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": "Veuillez fournir une liste d'IDs valide et non vide"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not all(isinstance(i, int) for i in ids):
            return Response(
                {"error": "Tous les IDs doivent être des entiers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = self.get_queryset().filter(id__in=ids)
        found_count = queryset.count()

        if found_count == 0:
            return Response(
                {"error": "Aucun élément trouvé avec les IDs fournis"},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            for instance in queryset:
                self.verifier_suppression(instance)
            deleted_count, _ = queryset.delete()

        return Response({
            "message": f"{deleted_count} élément(s) supprimé(s) avec succès",
            "deleted_count": deleted_count
        }, status=status.HTTP_200_OK)


# ============================================================
# UTILISATEURS & RÔLES
# ============================================================

class _UserLinkViewSet(BaseViewSet):
    """
    Lignes d'historique rattachées à un user (poste, catégorie, service, agence).
    Lecture : gestionnaires et administrateurs. Écriture : administrateurs.
    Le user d'une ligne existante ne peut pas être changé.
    """
    permission_classes = [ReadGestionnaireWriteAdmin]

    def perform_update(self, serializer):
        instance = serializer.instance
        new_user = serializer.validated_data.get('user', instance.user)
        if instance.user_id != new_user.id:
            raise PermissionDenied(
                f"Impossible de changer le user d'un {instance.__class__.__name__} existant."
            )
        super().perform_update(serializer)


class UserPosteViewSet(_UserLinkViewSet):
    queryset = UserPoste.objects.select_related(
        'user', 'poste', 'statut'
    ).order_by('id')
    serializer_class = UserPosteSerializer
    filterset_fields = ['user', 'poste', 'statut']


class UserCategoriesalarieViewSet(_UserLinkViewSet):
    queryset = UserCategoriesalarie.objects.select_related(
        'user', 'categoriesalarie', 'statut'
    ).order_by('id')
    serializer_class = UserCategoriesalarieSerializer
    filterset_fields = ['user', 'categoriesalarie', 'statut']


class UserServiceViewSet(_UserLinkViewSet):
    queryset = (
        UserService.objects
        .select_related('user', 'service', 'statut')
        .order_by('id')
    )
    serializer_class = UserServiceSerializer
    filterset_fields = ['user', 'service', 'statut']


class UserAgenceViewSet(_UserLinkViewSet):
    queryset = (
        UserAgence.objects
        .select_related('user', 'agence', 'statut')
        .order_by('id')
    )
    serializer_class = UserAgenceSerializer
    filterset_fields = ['user', 'agence', 'statut']


def _verifier_peut_gerer(request, cible):
    """
    Règles de gestion des comptes :
    - personne ne peut se désactiver / se supprimer lui-même ;
    - seul un super_admin peut modifier un compte super_admin.
    """
    if cible.is_superuser or cible.groups.filter(name=ROLE_SUPER_ADMIN).exists():
        if not is_super_admin(request.user):
            raise PermissionDenied(
                "Seul un super administrateur peut modifier ce compte."
            )


def _supprimer_comptes(users):
    """
    Supprime les comptes (et leurs affectations). Un compte désigné comme N+1
    ou référencé ailleurs ne peut pas être supprimé : il faut le désactiver.
    """
    from django.db.models.deletion import ProtectedError, RestrictedError
    try:
        with transaction.atomic():
            for user in users:
                user.delete()
    except (ProtectedError, RestrictedError):
        raise ValidationError("Ce compte est encore référencé (N+1 désigné d'autres collaborateurs…) : "
                              "désactivez-le plutôt que de le supprimer.")
    return len(users)


class UserFilter(django_filters.FilterSet):
    """
    Recherche avancée des comptes (page Utilisateurs) sur toutes les données :
    texte partiel, rôle, et affectations en cours (agence, service, poste, catégorie).
    """
    nom       = django_filters.CharFilter(lookup_expr='icontains')
    prenom    = django_filters.CharFilter(lookup_expr='icontains')
    username  = django_filters.CharFilter(lookup_expr='icontains')
    email     = django_filters.CharFilter(lookup_expr='icontains')
    groupe    = django_filters.NumberFilter(field_name='groups')
    agence           = django_filters.NumberFilter(method='filtrer_affectation')
    service          = django_filters.NumberFilter(method='filtrer_affectation')
    poste            = django_filters.NumberFilter(method='filtrer_affectation')
    categoriesalarie = django_filters.NumberFilter(method='filtrer_affectation')
    sans_agence      = django_filters.BooleanFilter(method='filtrer_sans_agence')

    class Meta:
        model  = User
        fields = ['statut', 'is_active']

    def filtrer_sans_agence(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(useragence__isnull=value).distinct()

    def filtrer_affectation(self, queryset, name, value):
        relation = {'agence': 'useragence', 'service': 'userservice', 'poste': 'userposte',
                    'categoriesalarie': 'usercategoriesalarie'}[name]
        en_cours = Q(**{f'{relation}__date_fin__isnull': True}) | Q(**{f'{relation}__date_fin__gte': timezone.now()})
        return queryset.filter(Q(**{f'{relation}__{name}': value}) & en_cours).distinct()


def _verifier_aucune_validation_en_attente(user):
    """Décision 7 : un valideur qui a des validations en attente ne peut pas être désactivé."""
    from rest_framework.exceptions import ValidationError
    from workflow.models import Tache
    taches = list(Tache.objects.filter(valideur=user, etat='en_attente')
                  .select_related('etape_instance__instance__demande', 'etape_instance__etape')[:20])
    if taches:
        liste = ', '.join(f"{t.etape_instance.instance.demande.reference} ({t.etape_instance.etape.libelle})" for t in taches)
        raise ValidationError({'is_active': f"{user.nom} {user.prenom} a {len(taches)} validation(s) en attente : {liste}. "
                                            "Réaffectez-les depuis la fiche de chaque demande avant de désactiver le compte."})


class UserViewSet(BaseViewSet):
    """
    Gestion des comptes : réservée aux administrateurs.
    Exceptions : /me/, /logout/ et /changer-mot-de-passe/ (utilisateur connecté),
    mot de passe oublié (public, avec limitation de débit).
    """
    # queryset factice requis par le router DRF pour déterminer le basename.
    # La vraie logique est dans get_queryset() ci-dessous.
    queryset = User.objects.none()
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]
    # Défini par action (mot de passe oublié) ; doit exister au niveau classe
    # pour pouvoir être passé en argument de @action.
    throttle_scope = None
    filterset_class  = UserFilter
    search_fields    = ['nom', 'prenom', 'email', 'username']
    ordering_fields  = ['id', 'nom', 'prenom', 'username', 'created_at']

    @staticmethod
    def _prefetch(qs):
        from django.db.models import Prefetch
        return qs.select_related('statut').prefetch_related(
            Prefetch('userservice_set',
                     queryset=UserService.objects.select_related('service', 'statut')),
            Prefetch('useragence_set',
                     queryset=UserAgence.objects.select_related('agence', 'statut')),
            Prefetch('userposte_set',
                     queryset=UserPoste.objects.select_related('poste', 'statut')),
            Prefetch('usercategoriesalarie_set',
                     queryset=UserCategoriesalarie.objects.select_related('categoriesalarie', 'statut')),
            'groups',
        )

    def get_queryset(self):
        return self._prefetch(User.objects.all()).order_by('id')

    def list(self, request, *args, **kwargs):
        """
        Pagine d'abord sur un queryset léger, puis recharge uniquement les
        users de la page courante avec tous les prefetch.
        """
        base_qs = self.filter_queryset(User.objects.select_related('statut').order_by('id'))
        page_qs = self.paginate_queryset(base_qs)

        if page_qs is not None:
            user_ids = [u.id for u in page_qs]
            users_avec_prefetch = list(
                self._prefetch(User.objects.filter(id__in=user_ids))
            )
            # Même ordre que la page (tri demandé par ?ordering=)
            rang = {pk: i for i, pk in enumerate(user_ids)}
            users_avec_prefetch.sort(key=lambda u: rang[u.id])
            serializer = self.get_serializer(users_avec_prefetch, many=True)
            return self.get_paginated_response(serializer.data)

        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def perform_update(self, serializer):
        _verifier_peut_gerer(self.request, serializer.instance)
        if serializer.instance.pk == self.request.user.pk:
            # Éviter qu'un administrateur se bloque lui-même
            if serializer.validated_data.get('is_active') is False:
                raise PermissionDenied("Vous ne pouvez pas désactiver votre propre compte.")
        if serializer.instance.is_active and serializer.validated_data.get('is_active') is False:
            _verifier_aucune_validation_en_attente(serializer.instance)
            groupes = serializer.validated_data.get('groups')
            if groupes is not None and not self.request.user.is_superuser \
                    and not {g.name for g in groupes} & ADMIN_ROLES:
                raise PermissionDenied("Vous ne pouvez pas retirer vos propres droits d'administrateur.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.pk == self.request.user.pk:
            raise PermissionDenied("Vous ne pouvez pas supprimer votre propre compte.")
        _verifier_peut_gerer(self.request, instance)
        _supprimer_comptes([instance])

    @action(detail=False, methods=['delete'], permission_classes=[IsAdminRole])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            return Response(
                {"error": "Veuillez fournir une liste d'IDs entiers non vide"},
                status=status.HTTP_400_BAD_REQUEST
            )
        if request.user.pk in ids:
            return Response(
                {"error": "Vous ne pouvez pas supprimer votre propre compte."},
                status=status.HTTP_400_BAD_REQUEST
            )
        users = User.objects.filter(id__in=ids)
        for user in users:
            _verifier_peut_gerer(request, user)
        deleted_count = _supprimer_comptes(list(users))
        return Response({
            "message": f"{deleted_count} élément(s) supprimé(s) avec succès",
            "deleted_count": deleted_count
        })

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Création d'un compte par un administrateur (plus d'inscription publique)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user_created=request.user, user_updated=request.user)
        return Response(
            {"message": "Utilisateur créé avec succès"},
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """GET /users/me/ : profil de l'utilisateur connecté."""
        user = self._prefetch(User.objects.filter(pk=request.user.pk)).get()
        return Response(self.get_serializer(user).data)

    @action(detail=False, methods=['post', 'delete'], url_path='me/photo',
            permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def ma_photo(self, request):
        """
        POST   /api/api/users/me/photo/   champ « photo » (JPEG, PNG ou WebP, 5 Mo max)
        DELETE /api/api/users/me/photo/   retire la photo
        L'image est vérifiée, redressée et réduite (512 px, JPEG) avant l'enregistrement.
        """
        user = request.user
        if request.method == 'DELETE':
            if user.photo:
                user.photo.delete(save=False)
            user.photo = None
            user.save(update_fields=['photo', 'updated_at'])
            return Response(self.get_serializer(user).data)

        fichier = request.FILES.get('photo')
        if not fichier:
            raise ValidationError("Choisissez une photo.")
        if fichier.size > 5 * 1024 * 1024:
            raise ValidationError("La photo ne doit pas dépasser 5 Mo.")
        from PIL import Image, ImageOps, UnidentifiedImageError
        from django.core.files.base import ContentFile
        try:
            image = Image.open(fichier)
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValidationError("Formats acceptés : JPEG, PNG ou WebP.")
            image.verify()
            fichier.seek(0)
            image = ImageOps.exif_transpose(Image.open(fichier)).convert('RGB')
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError("Le fichier n'est pas une image valide (JPEG, PNG ou WebP).")
        image.thumbnail((512, 512))
        sortie = BytesIO()
        image.save(sortie, format='JPEG', quality=85)
        ancien = user.photo.name if user.photo else None
        user.photo.save(f'user_{user.pk}.jpg', ContentFile(sortie.getvalue()), save=False)
        user.save(update_fields=['photo', 'updated_at'])
        if ancien and ancien != user.photo.name:
            user.photo.storage.delete(ancien)
        return Response(self.get_serializer(user).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        """
        POST /api/api/users/logout/   body : { "refresh": "<refresh token>" }
        Révoque le refresh token et enregistre l'heure de déconnexion.
        """
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # déjà expiré ou révoqué : la déconnexion reste valide
        request.user.last_logout = timezone.now()
        request.user.save(update_fields=['last_logout'])
        return Response({'message': 'Déconnecté.'})

    @action(detail=True, methods=['get'])
    def connection_history(self, request, pk=None):
        user = self.get_object()
        connecte = bool(
            user.last_login and
            (not user.last_logout or user.last_login > user.last_logout)
        )
        return Response({
            'username':             user.username,
            'derniere_connexion':   user.last_login.strftime("%Y-%m-%d %H:%M:%S") if user.last_login else None,
            'derniere_deconnexion': user.last_logout.strftime("%Y-%m-%d %H:%M:%S") if user.last_logout else None,
            'statut_actuel':        'Connecté' if connecte else 'Déconnecté',
            'compte_actif':         user.is_active,
        })

    def _changer_activation(self, request, users, actif):
        for user in users:
            if not actif and user.pk == request.user.pk:
                raise PermissionDenied("Vous ne pouvez pas désactiver votre propre compte.")
            _verifier_peut_gerer(request, user)
            if not actif:
                _verifier_aucune_validation_en_attente(user)
        return User.objects.filter(pk__in=[u.pk for u in users]).update(is_active=actif)

    @action(detail=True, methods=['patch'], url_path='activer')
    def activer(self, request, pk=None):
        user = self.get_object()
        self._changer_activation(request, [user], True)
        return Response({'message': f'Utilisateur {user.username} activé avec succès.'})

    @action(detail=True, methods=['patch'], url_path='desactiver')
    def desactiver(self, request, pk=None):
        user = self.get_object()
        self._changer_activation(request, [user], False)
        return Response({'message': f'Utilisateur {user.username} désactivé avec succès.'})

    @action(detail=False, methods=['patch'], url_path='activer-multiple')
    def activer_multiple(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'Aucun ID fourni.'}, status=400)
        count = self._changer_activation(request, list(User.objects.filter(id__in=ids)), True)
        return Response({'message': f'{count} utilisateur(s) activé(s) avec succès.'})

    @action(detail=False, methods=['patch'], url_path='desactiver-multiple')
    def desactiver_multiple(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'Aucun ID fourni.'}, status=400)
        count = self._changer_activation(request, list(User.objects.filter(id__in=ids)), False)
        return Response({'message': f'{count} utilisateur(s) désactivé(s) avec succès.'})

    # ── Mot de passe oublié (public) ─────────────────────────
    # Le code (6 chiffres) et le jeton de réinitialisation sont générés avec
    # le module secrets, stockés dans le cache partagé, et le nombre
    # d'essais est limité. Les réponses ne révèlent pas si un compte existe.

    OTP_TTL          = 600   # 10 minutes
    OTP_MAX_ESSAIS   = 5
    # Demandes de code par matricule : 3 au plus sur 30 minutes (fenêtre ouverte à la 1re demande)
    DEMANDES_MAX     = 3
    DEMANDES_FENETRE = 1800
    MESSAGE_ENVOI    = "Si ce compte existe, un code a été envoyé par SMS au numéro enregistré."

    def _limiter_demandes(self, username):
        """3 demandes de code par matricule sur 30 minutes ; au-delà, 429 avec le délai restant."""
        cle = f'reset_demandes_{username.lower()}'
        maintenant = timezone.now().timestamp()
        entree = cache.get(cle) or {'debut': maintenant, 'nombre': 0}
        if entree['nombre'] >= self.DEMANDES_MAX:
            reste = max(1, math.ceil((entree['debut'] + self.DEMANDES_FENETRE - maintenant) / 60))
            return Response(
                {'error': f"Trop de demandes de code pour ce matricule. Veuillez réessayer dans {reste} minute{'s' if reste > 1 else ''}.",
                 'reessayer_dans_minutes': reste},
                status=status.HTTP_429_TOO_MANY_REQUESTS)
        entree['nombre'] += 1
        restant_fenetre = max(1, int(entree['debut'] + self.DEMANDES_FENETRE - maintenant))
        cache.set(cle, entree, timeout=restant_fenetre)
        return None

    @staticmethod
    def _envoyer_sms(contact, texte):
        if not (settings.ALLMYSMS_LOGIN and settings.ALLMYSMS_API_KEY):
            logger.error("AllMySMS non configuré (ALLMYSMS_LOGIN / ALLMYSMS_API_KEY absents du .env)")
            return False
        try:
            reponse = requests.post(
                'https://api.allmysms.com/sms/send',
                json={
                    'login':  settings.ALLMYSMS_LOGIN,
                    'apiKey': settings.ALLMYSMS_API_KEY,
                    'from':   settings.ALLMYSMS_SENDER,
                    'to':     contact,
                    'text':   texte,
                },
                timeout=10,
            )
        except requests.RequestException as e:
            logger.error("Envoi SMS impossible : %s", e)
            return False
        if reponse.status_code not in (200, 201):
            logger.error("AllMySMS a répondu %s : %s", reponse.status_code, reponse.text[:200])
            return False
        return True

    @action(
        detail=False, methods=['post'],
        url_path='forgot-password',
        permission_classes=[AllowAny],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope='password_reset',
    )
    def forgot_password(self, request):
        """
        POST /api/api/users/forgot-password/
        Génère un code OTP et l'envoie par SMS au contact du compte.
        """
        username = str(request.data.get('username', '')).strip()
        if not username:
            return Response(
                {'error': 'Le nom d\'utilisateur est requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        # Limite par matricule, comptée que le compte existe ou non (rien n'est révélé)
        refus = self._limiter_demandes(username)
        if refus:
            return refus

        user = User.objects.filter(username=username, is_active=True).first()
        contact = (getattr(user, 'contact', '') or '').strip() if user else ''

        if not user or not contact:
            # Même réponse que si le SMS était parti : on ne révèle pas
            # quels identifiants existent.
            return Response({'message': self.MESSAGE_ENVOI}, status=status.HTTP_200_OK)

        code = f"{secrets.randbelow(10 ** 6):06d}"
        cache.set(f'reset_code_{username}', {'code': code, 'essais': 0}, timeout=self.OTP_TTL)

        if not self._envoyer_sms(
            contact,
            f'UbiFlow - Votre code de réinitialisation : {code}\nValable 10 minutes.',
        ):
            cache.delete(f'reset_code_{username}')
            return Response(
                {'error': 'Service SMS indisponible. Réessayez plus tard.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'message':        self.MESSAGE_ENVOI,
            'contact_masque': contact[-4:].rjust(len(contact), '*'),
        }, status=status.HTTP_200_OK)

    @action(
        detail=False, methods=['post'],
        url_path='verify-code',
        permission_classes=[AllowAny],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope='password_reset',
    )
    def verify_code(self, request):
        """
        POST /api/api/users/verify-code/
        Vérifie le code OTP (5 essais maximum) et renvoie un jeton de réinitialisation.
        """
        username = str(request.data.get('username', '')).strip()
        code     = str(request.data.get('code', '')).strip()

        if not username or not code:
            return Response(
                {'error': 'Identifiant et code requis.'},
                status=status.HTTP_400_BAD_REQUEST)

        cache_key = f'reset_code_{username}'
        entree    = cache.get(cache_key)

        if not entree:
            return Response(
                {'error': 'Code expiré ou invalide. Recommencez.'},
                status=status.HTTP_400_BAD_REQUEST)

        if not hmac.compare_digest(entree['code'], code):
            entree['essais'] += 1
            if entree['essais'] >= self.OTP_MAX_ESSAIS:
                cache.delete(cache_key)
                return Response(
                    {'error': 'Trop de tentatives. Demandez un nouveau code.'},
                    status=status.HTTP_400_BAD_REQUEST)
            cache.set(cache_key, entree, timeout=self.OTP_TTL)
            return Response(
                {'error': 'Code incorrect.'},
                status=status.HTTP_400_BAD_REQUEST)

        reset_token = secrets.token_urlsafe(32)
        cache.set(f'reset_token_{username}', reset_token, timeout=self.OTP_TTL)
        cache.delete(cache_key)

        return Response({
            'message':     'Code vérifié.',
            'reset_token': reset_token,
        }, status=status.HTTP_200_OK)

    @action(
        detail=False, methods=['post'],
        url_path='reset-password',
        permission_classes=[AllowAny],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope='password_reset',
    )
    def reset_password(self, request):
        """
        POST /api/api/users/reset-password/
        Réinitialise le mot de passe avec le jeton obtenu par verify-code.
        """
        username    = str(request.data.get('username', '')).strip()
        reset_token = str(request.data.get('reset_token', '')).strip()
        nouveau_mdp = str(request.data.get('password', ''))

        if not username or not reset_token or not nouveau_mdp:
            return Response(
                {'error': 'Données incomplètes.'},
                status=status.HTTP_400_BAD_REQUEST)

        token_stocke = cache.get(f'reset_token_{username}')
        if not token_stocke or not hmac.compare_digest(token_stocke, reset_token):
            return Response(
                {'error': 'Session expirée. Recommencez depuis le début.'},
                status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(username=username, is_active=True).first()
        if not user:
            return Response(
                {'error': 'Session expirée. Recommencez depuis le début.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password_custom(nouveau_mdp)
        except DjangoValidationError as e:
            return Response(
                {'error': e.messages},
                status=status.HTTP_400_BAD_REQUEST)

        user.set_password(nouveau_mdp)
        user.save()
        cache.delete(f'reset_token_{username}')

        return Response(
            {'message': 'Mot de passe réinitialisé avec succès.'},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='changer-mot-de-passe',
            permission_classes=[IsAuthenticated])
    def changer_mot_de_passe(self, request, pk=None):
        """
        PATCH /api/api/users/{id}/changer-mot-de-passe/
        - Utilisateur : uniquement SON mot de passe, ancien mot de passe obligatoire
        - super_admin / admin : celui de n'importe qui (sauf super_admin, réservé aux super_admin)
        Règles : 8 caractères min | 1 majuscule | 1 chiffre | 1 caractère spécial
        """
        user         = self.get_object()
        nouveau_mdp  = request.data.get('password')
        old_password = request.data.get('old_password')
        admin        = is_admin(request.user)

        if request.user.id != user.id:
            if not admin:
                return Response(
                    {'error': 'Vous ne pouvez modifier que votre propre mot de passe.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            _verifier_peut_gerer(request, user)

        # Pour son propre compte, l'ancien mot de passe est toujours exigé
        if request.user.id == user.id:
            if not old_password:
                return Response(
                    {'error': 'L\'ancien mot de passe est requis.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not user.check_password(old_password):
                return Response(
                    {'error': 'Mot de passe actuel incorrect.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if not nouveau_mdp:
            return Response(
                {'error': 'Le nouveau mot de passe est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            validate_password_custom(nouveau_mdp)
        except DjangoValidationError as e:
            return Response(
                {'error': e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(nouveau_mdp)
        user.save()
        return Response({'message': 'Mot de passe modifié avec succès.'})


class AllUserNopginListAPIView(ListAPIView):
    """Tous les utilisateurs (listes déroulantes) : gestionnaires et admins."""
    serializer_class   = UserSerializer
    permission_classes = [IsGestionnaireRole]
    pagination_class   = None

    def get_queryset(self):
        # Prefetch des historiques : évite plusieurs requêtes SQL par agent
        return UserViewSet._prefetch(User.objects.all()).order_by('nom', 'prenom')


class GroupViewSet(viewsets.ModelViewSet):
    """
    Rôles (groupes Django) : réservé aux administrateurs.
    Les rôles de l'application ne peuvent
    pas être supprimés ni renommés.
    """
    queryset = Group.objects.all().order_by('id')
    serializer_class = GroupSerializer
    permission_classes = [IsAdminRole]

    ROLES_SYSTEME = set(LIBELLES_ROLES)
    LIBELLES = LIBELLES_ROLES
    ordering_fields = ['id', 'name']

    def get_queryset(self):
        qs = super().get_queryset()
        terme = (self.request.query_params.get('search') or '').strip().lower()
        if terme:
            francais = [nom for nom, lib in self.LIBELLES.items() if terme in lib.lower()]
            qs = qs.filter(Q(name__icontains=terme) | Q(name__in=francais))
        return qs

    def _proteger(self, group):
        if group.name in self.ROLES_SYSTEME:
            raise PermissionDenied(f"Le rôle « {group.name} » est un rôle système.")

    def perform_update(self, serializer):
        self._proteger(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._proteger(instance)
        instance.delete()

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])

        if not isinstance(ids, list) or not ids:
            return Response(
                {"error": "Veuillez fournir une liste d'IDs valide et non vide"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not all(isinstance(i, int) for i in ids):
            return Response(
                {"error": "Tous les IDs doivent être des entiers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        groups = Group.objects.filter(id__in=ids)
        for group in groups:
            self._proteger(group)
        deleted_count, _ = groups.delete()

        return Response({
            "message": f"{deleted_count} rôle(s) supprimé(s) avec succès",
            "deleted_count": deleted_count
        })


class GroupListAPIView(ListAPIView):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None


# ============================================================
# RÉFÉRENTIELS
# ============================================================

class AgenceViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'nom_agence'
    queryset = Agence.objects.all().order_by('id')
    serializer_class = AgenceSerializer
    filterset_fields = ['nom_agence']
    search_fields = ['nom_agence', 'code']
    ordering_fields = ['id', 'nom_agence', 'created_at']



class AllAgenceNopginListAPIView(ListAPIView):
    queryset = Agence.objects.all()
    serializer_class = AgenceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class StatutViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'libelle_statut'
    search_fields = ['libelle_statut']
    queryset = Statut.objects.all().order_by('id')
    serializer_class = StatutSerializer


class PublicStatutListAPIView(ListAPIView):
    queryset = Statut.objects.all()
    serializer_class = StatutSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class ServiceViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'libelle_service'
    search_fields = ['libelle_service', 'code']
    filterset_fields = ['parent']
    ordering_fields = ['id', 'libelle_service', 'code']
    queryset = Service.objects.select_related('parent').order_by('id')
    serializer_class = ServiceSerializer


class ServiceListAPIView(ListAPIView):
    queryset = Service.objects.select_related('parent').order_by('libelle_service')
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class FonctionViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'libelle'
    queryset = Fonction.objects.all().order_by('id')
    serializer_class = FonctionSerializer
    filterset_fields = ['libelle']
    search_fields = ['libelle']
    ordering_fields = ['id', 'libelle', 'created_at']


class FonctionListAPIView(ListAPIView):
    queryset = Fonction.objects.all()
    serializer_class = FonctionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class CategoriesalarieViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'libelle'
    queryset = Categoriesalarie.objects.all().order_by('id')
    serializer_class = CategoriesalarieSerializer
    filterset_fields = ['libelle']
    search_fields = ['libelle']
    ordering_fields = ['id', 'libelle', 'created_at']


class CategoriesalarieListAPIView(ListAPIView):
    queryset = Categoriesalarie.objects.all()
    serializer_class = CategoriesalarieSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class PosteViewSet(BaseViewSet):
    proteger_references = True
    champ_libelle = 'libelle'
    queryset = Poste.objects.select_related('fonction', 'service').all().order_by('id')
    serializer_class = PosteSerializer
    filterset_fields = ['libelle', 'fonction', 'service']
    search_fields    = ['libelle']
    ordering_fields  = ['id', 'libelle', 'created_at']


class PosteListAPIView(ListAPIView):
    queryset = Poste.objects.select_related('fonction', 'service').all()
    serializer_class = PosteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class AnnuaireView(ListAPIView):
    """
    GET /annuaire/?q=  collaborateurs actifs (id, matricule, nom, prénom) pour les choix
    ouverts à tous (délégataire…). Sans donnée d'organisation ni de contact.
    """
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        qs = User.objects.filter(is_active=True).order_by('nom', 'prenom')
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(username__icontains=q))
        return Response([{'id': u.id, 'matricule': u.username, 'nom': u.nom, 'prenom': u.prenom,
                          'libelle': f"{u.nom} {u.prenom} ({u.username})".strip()} for u in qs[:200]])
