"""
Permissions par rôle.

Les rôles sont des groupes Django :
    super_admin  → tout, y compris gérer les autres administrateurs
    admin        → administration de l'application (utilisateurs, paramètres)
    gestionnaire → consultation des paramètres et des utilisateurs de ses agences
    employe      → utilisateur standard

Un superuser Django est considéré comme super_admin.
"""

from rest_framework import permissions

ROLE_SUPER_ADMIN  = 'super_admin'
ROLE_ADMIN        = 'admin'
ROLE_GESTIONNAIRE = 'gestionnaire'
ROLE_EMPLOYE      = 'employe'

ADMIN_ROLES        = {ROLE_SUPER_ADMIN, ROLE_ADMIN}
GESTIONNAIRE_ROLES = ADMIN_ROLES | {ROLE_GESTIONNAIRE}

# Libellés des rôles (écrans d'administration, messages)
LIBELLES_ROLES = {
    ROLE_SUPER_ADMIN: 'Super administrateur', ROLE_ADMIN: 'Administrateur',
    ROLE_GESTIONNAIRE: 'Gestionnaire', ROLE_EMPLOYE: 'Employé',
}


def get_roles(user):
    """Noms des groupes de l'utilisateur (mis en cache sur l'objet pour la requête)."""
    if not user or not user.is_authenticated:
        return set()
    if not hasattr(user, '_roles_cache'):
        user._roles_cache = set(user.groups.values_list('name', flat=True))
    return user._roles_cache


def is_super_admin(user):
    return bool(user and user.is_authenticated and
                (user.is_superuser or ROLE_SUPER_ADMIN in get_roles(user)))


def is_admin(user):
    return bool(user and user.is_authenticated and
                (user.is_superuser or get_roles(user) & ADMIN_ROLES))


def is_gestionnaire(user):
    """Vrai pour les gestionnaires ET les administrateurs."""
    return bool(user and user.is_authenticated and
                (user.is_superuser or get_roles(user) & GESTIONNAIRE_ROLES))


def agences_gerees(user):
    """
    Agences dont un gestionnaire s'occupe : None pour un administrateur
    (toutes), sinon les agences auxquelles il est rattaché aujourd'hui
    (ensemble vide s'il n'en a aucune).
    """
    if is_admin(user):
        return None
    if not hasattr(user, '_agences_cache'):
        from django.db.models import Q
        from django.utils import timezone
        from .models import UserAgence
        maintenant = timezone.now()
        user._agences_cache = set(
            UserAgence.objects.filter(user=user, date_debut__lte=maintenant)
            .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=maintenant))
            .values_list('agence_id', flat=True)
        )
    return user._agences_cache


class IsAuthenticated(permissions.BasePermission):
    """Tout utilisateur connecté."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdminRole(permissions.BasePermission):
    """Réservé aux rôles super_admin / admin."""
    message = "Action réservée aux administrateurs."

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsGestionnaireRole(permissions.BasePermission):
    """Réservé aux gestionnaires et administrateurs."""
    message = "Action réservée aux gestionnaires."

    def has_permission(self, request, view):
        return is_gestionnaire(request.user)


class ReadAuthenticatedWriteAdmin(permissions.BasePermission):
    """Lecture : tout utilisateur connecté. Écriture : administrateurs."""
    message = "Modification réservée aux administrateurs."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_admin(request.user)


class ReadGestionnaireWriteAdmin(permissions.BasePermission):
    """Lecture : gestionnaires et administrateurs. Écriture : administrateurs."""
    message = "Accès réservé aux gestionnaires."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return is_gestionnaire(request.user)
        return is_admin(request.user)
