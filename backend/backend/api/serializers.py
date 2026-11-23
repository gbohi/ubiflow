from rest_framework import serializers
from django.contrib.auth.models import Group
from .models import *
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
import re


def nom_complet(user):
    """« Nom Prénom » de l'agent (champs nom/prenom du modèle User), sinon son identifiant."""
    nom = f"{user.nom or ''} {user.prenom or ''}".strip()
    if not nom:
        nom = f"{user.first_name} {user.last_name}".strip()
    return nom or user.username


def agence_actuelle(user, a_date=None):
    """
    Agence de l'agent : ligne UserAgence active à la date donnée (aujourd'hui
    par défaut), sinon la plus récente. Utilise le prefetch si présent.
    """
    a_date = a_date or timezone.now()
    lignes = list(user.useragence_set.all())
    if not lignes:
        return None
    actives = [l for l in lignes
               if l.date_debut <= a_date and (l.date_fin is None or l.date_fin >= a_date)]
    ligne = max(actives or lignes, key=lambda l: l.date_debut)
    return ligne.agence


class _PeriodeMixin:
    """
    Lignes d'historique d'un agent (département, agence, poste, catégorie) :
      - la date de fin ne peut pas précéder la date de début ;
      - si `periode_exclusive`, deux lignes du même agent ne peuvent pas se
        chevaucher (un agent n'a qu'une agence / une catégorie salarié à la
        fois).
    """
    periode_exclusive = False
    libelle_periode = 'ligne'
    # Champ qui identifie « le même propriétaire » pour le chevauchement
    cle_periode = 'user'
    proprietaire = "de l'agent"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = getattr(self, 'instance', None)
        debut = attrs.get('date_debut', getattr(inst, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(inst, 'date_fin', None))
        cle = self.cle_periode
        proprio = attrs.get(cle, getattr(inst, cle, None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                {'date_fin': "La date de fin doit être postérieure ou égale à la date de début."})
        if self.periode_exclusive and proprio and debut:
            autres = self.Meta.model.objects.filter(**{cle: proprio})
            for autre_cle in getattr(self, 'cles_periode_supplementaires', ()):
                valeur = attrs.get(autre_cle, getattr(inst, autre_cle, None))
                autres = autres.filter(**{autre_cle: valeur})
            if inst is not None:
                autres = autres.exclude(pk=inst.pk)
            # Chevauchement : [debut, fin] ∩ [a.debut, a.fin] ≠ ∅ (fin vide = en cours)
            autres = autres.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=debut))
            if fin:
                autres = autres.filter(date_debut__lte=fin)
            if autres.exists():
                raise serializers.ValidationError(
                    f"Cette période chevauche une autre {self.libelle_periode} {self.proprietaire} : "
                    "renseignez la date de fin de la précédente avant d'en ajouter une nouvelle.")
        return attrs


# ============================================================
# VALIDATION MOT DE PASSE PERSONNALISÉE
# ============================================================

def validate_password_custom(password):
    """
    Valide les exigences de complexité du mot de passe :
    - 8 caractères minimum
    - Au moins 1 majuscule
    - Au moins 1 chiffre
    - Au moins 1 caractère spécial
    Lève DjangoValidationError si une règle n'est pas respectée.
    """
    errors = []
    if len(password) < 8:
        errors.append("Le mot de passe doit contenir au moins 8 caractères.")
    if not re.search(r'[A-Z]', password):
        errors.append("Le mot de passe doit contenir au moins une majuscule.")
    if not re.search(r'[0-9]', password):
        errors.append("Le mot de passe doit contenir au moins un chiffre.")
    if not re.search(r'[!@#$%^&*()\[\]{}\-_=+\\|;:\'",.<>?/`~]', password):
        errors.append("Le mot de passe doit contenir au moins un caractère spécial.")
    if errors:
        raise DjangoValidationError(errors)


# ============================================================
# USERS & GROUPES
# ============================================================

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


# ============================================================
# RÉFÉRENTIELS
# ============================================================

class AgenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agence
        fields = '__all__'


class StatutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Statut
        fields = '__all__'


class ServiceSerializer(serializers.ModelSerializer):
    """Département."""
    class Meta:
        model = Service
        fields = '__all__'


class FonctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fonction
        fields = '__all__'


class CategoriesalarieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoriesalarie
        fields = '__all__'


class PosteSerializer(serializers.ModelSerializer):
    fonction_libelle = serializers.ReadOnlyField(source='fonction.libelle')
    service_libelle  = serializers.ReadOnlyField(source='service.libelle_service')

    class Meta:
        model  = Poste
        fields = '__all__'


# ============================================================
# USER & SOUS-MODÈLES
# ============================================================

class UserServiceSerializer(_PeriodeMixin, serializers.ModelSerializer):
    libelle_periode = 'affectation de département'
    service_id      = serializers.ReadOnlyField(source='service.id')
    service_libelle = serializers.ReadOnlyField(source='service.libelle_service')
    statut_id       = serializers.ReadOnlyField(source='statut.id')
    statut_libelle  = serializers.ReadOnlyField(source='statut.libelle_statut')
    user_id         = serializers.ReadOnlyField(source='user.id')
    user_username   = serializers.ReadOnlyField(source='user.username')
    user_nom        = serializers.ReadOnlyField(source='user.nom')
    user_prenom     = serializers.ReadOnlyField(source='user.prenom')
    user_email      = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model  = UserService
        fields = '__all__'


class UserAgenceSerializer(_PeriodeMixin, serializers.ModelSerializer):
    periode_exclusive = True
    libelle_periode = 'affectation d\'agence'
    agence_id      = serializers.ReadOnlyField(source='agence.id')
    agence_nom     = serializers.ReadOnlyField(source='agence.nom_agence')
    statut_id      = serializers.ReadOnlyField(source='statut.id')
    statut_libelle = serializers.ReadOnlyField(source='statut.libelle_statut')
    user_id        = serializers.ReadOnlyField(source='user.id')
    user_username  = serializers.ReadOnlyField(source='user.username')
    user_nom       = serializers.ReadOnlyField(source='user.nom')
    user_prenom    = serializers.ReadOnlyField(source='user.prenom')
    user_email     = serializers.ReadOnlyField(source='user.email')

    class Meta:
        model  = UserAgence
        fields = '__all__'


class UserPosteSerializer(_PeriodeMixin, serializers.ModelSerializer):
    libelle_periode = 'affectation de poste'
    statut_libelle = serializers.ReadOnlyField(source='statut.libelle_statut')
    poste_libelle  = serializers.ReadOnlyField(source='poste.libelle')

    class Meta:
        model  = UserPoste
        fields = '__all__'


class UserCategoriesalarieSerializer(_PeriodeMixin, serializers.ModelSerializer):
    periode_exclusive = True
    libelle_periode = 'catégorie salarié'
    statut_libelle           = serializers.ReadOnlyField(source='statut.libelle_statut')
    categoriesalarie_libelle = serializers.ReadOnlyField(source='categoriesalarie.libelle')

    class Meta:
        model  = UserCategoriesalarie
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, required=False)
    password2 = serializers.CharField(write_only=True, required=False)
    statut_libelle = serializers.ReadOnlyField(source='statut.libelle_statut')

    # Noms des rôles (super_admin, admin, gestionnaire, employe) :
    # les clients s'appuient dessus plutôt que sur des IDs de groupe.
    roles = serializers.SerializerMethodField()

    # ✅ groups : tableau d'IDs
    groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        required=False
    )

    # ── Listes complètes (historique) — utiles pour le détail et la modification
    user_services          = UserServiceSerializer(source='userservice_set', many=True, read_only=True)
    user_agences           = UserAgenceSerializer(source='useragence_set', many=True, read_only=True)
    user_postes            = UserPosteSerializer(source='userposte_set', many=True, read_only=True)
    user_categoriesalaries = UserCategoriesalarieSerializer(source='usercategoriesalarie_set', many=True, read_only=True)

    # ✅ Dernière ligne active de chaque relation — utiles pour la LISTE
    # Retourne directement l'objet le plus récent (date_debut max) ou null
    dernier_service          = serializers.SerializerMethodField()
    derniere_agence          = serializers.SerializerMethodField()
    dernier_poste            = serializers.SerializerMethodField()
    derniere_categoriesalarie = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'username', 'password', 'password2', 'email',
            'nom', 'prenom', 'contact', 'poste_telephone',
            'first_name', 'last_name',
            'statut', 'statut_libelle',
            'last_login', 'last_logout', 'is_active', 'is_superuser',
            'groups', 'roles',
            # Listes complètes
            'user_services', 'user_agences', 'user_postes',
            'user_categoriesalaries',
            # ✅ Dernières lignes (pour affichage en liste)
            'dernier_service', 'derniere_agence',
            'dernier_poste', 'derniere_categoriesalarie',
            'photo_url',
        ]
        read_only_fields = ['last_login', 'last_logout', 'is_superuser']

    # Photo de profil : envoyée par POST /users/me/photo/ (pas par ce formulaire)
    photo_url = serializers.SerializerMethodField()

    def get_photo_url(self, obj):
        if not obj.photo:
            return None
        # Paramètre de version : l'ancienne photo n'est pas resservie par le cache
        return f"{obj.photo.url}?v={int(obj.updated_at.timestamp())}" if obj.updated_at else obj.photo.url

    def get_roles(self, obj):
        return sorted(g.name for g in obj.groups.all())

    def validate_groups(self, groups):
        """Seul un super_admin peut attribuer le rôle super_admin."""
        from .permissions import ROLE_SUPER_ADMIN, is_super_admin
        request = self.context.get('request')
        if any(g.name == ROLE_SUPER_ADMIN for g in groups):
            if not (request and is_super_admin(request.user)):
                raise serializers.ValidationError(
                    "Seul un super administrateur peut attribuer le rôle super_admin."
                )
        return groups

    # ── Utilitaire interne ──────────────────────────────────────
    @staticmethod
    def _get_items(obj, related_name):
        """
        Récupère les items d'une relation inverse.
        Quand prefetch_related a été appelé sur le queryset parent,
        Django stocke les résultats dans obj.<related_name>.all()
        via le prefetch cache — pas de requête supplémentaire.
        Le list() dans get_queryset() garantit que le cache est peuplé.
        """
        return list(getattr(obj, related_name).all())

    @staticmethod
    def _derniere_ligne(items):
        """Retourne l'item avec la date_debut la plus récente."""
        if not items:
            return None
        return max(items, key=lambda x: x.date_debut or '')

    # ── SerializerMethodField — dernières lignes ────────────────

    def get_dernier_service(self, obj):
        ligne = self._derniere_ligne(self._get_items(obj, 'userservice_set'))
        if not ligne:
            return None
        return {
            'id':              ligne.id,
            'service':         ligne.service_id,
            'service_libelle': ligne.service.libelle_service if ligne.service else None,
            'date_debut':      str(ligne.date_debut) if ligne.date_debut else None,
            'statut':          ligne.statut_id,
            'statut_libelle':  ligne.statut.libelle_statut if ligne.statut else None,
        }

    def get_derniere_agence(self, obj):
        ligne = self._derniere_ligne(self._get_items(obj, 'useragence_set'))
        if not ligne:
            return None
        return {
            'id':             ligne.id,
            'agence':         ligne.agence_id,
            'agence_nom':     ligne.agence.nom_agence if ligne.agence else None,
            'date_debut':     str(ligne.date_debut) if ligne.date_debut else None,
            'statut':         ligne.statut_id,
            'statut_libelle': ligne.statut.libelle_statut if ligne.statut else None,
        }

    def get_dernier_poste(self, obj):
        ligne = self._derniere_ligne(self._get_items(obj, 'userposte_set'))
        if not ligne:
            return None
        return {
            'id':             ligne.id,
            'poste':          ligne.poste_id,
            'poste_libelle':  ligne.poste.libelle if ligne.poste else None,
            'date_debut':     str(ligne.date_debut) if ligne.date_debut else None,
            'statut':         ligne.statut_id,
            'statut_libelle': ligne.statut.libelle_statut if ligne.statut else None,
        }

    def get_derniere_categoriesalarie(self, obj):
        ligne = self._derniere_ligne(self._get_items(obj, 'usercategoriesalarie_set'))
        if not ligne:
            return None
        return {
            'id':                       ligne.id,
            'categoriesalarie':         ligne.categoriesalarie_id,
            'categoriesalarie_libelle': ligne.categoriesalarie.libelle if ligne.categoriesalarie else None,
            'date_debut':               str(ligne.date_debut) if ligne.date_debut else None,
            'statut':                   ligne.statut_id,
            'statut_libelle':           ligne.statut.libelle_statut if ligne.statut else None,
        }

    def validate(self, attrs):
        password  = attrs.get('password')
        password2 = attrs.get('password2')
        if self.instance is None and not password:
            # Sans mot de passe, le compte créé ne pourrait pas se connecter
            raise serializers.ValidationError(
                {"password": "Le mot de passe est obligatoire à la création du compte."})
        if password or password2:
            if password != password2:
                raise serializers.ValidationError(
                    {"password": "Les mots de passe ne correspondent pas."}
                )
            # ✅ Validation complexité mot de passe
            try:
                validate_password_custom(password)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": e.messages})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        groups   = validated_data.pop('groups', [])
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        # ✅ Assigner les groupes via la relation ManyToMany
        if groups:
            user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password', None)
        groups   = validated_data.pop('groups', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        # ✅ Mettre à jour les groupes si fournis
        if groups is not None:
            user.groups.set(groups)
        return user
