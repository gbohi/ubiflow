"""Erreurs métier : rendues en 400 / 403 par l'API (sous-classes des exceptions DRF)."""
from rest_framework.exceptions import PermissionDenied, ValidationError


class ErreurMetier(ValidationError):
    """Règle métier non respectée (message affiché tel quel à l'utilisateur)."""


class Interdit(PermissionDenied):
    """L'utilisateur n'a pas le droit de faire cette action."""
