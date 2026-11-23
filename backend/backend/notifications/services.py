"""Création des notifications (dans l'application ; push et e-mail au lot 6)."""
from django.contrib.auth import get_user_model

from .models import Notification


def notifier(destinataires, evenement, titre, message='', demande=None, lien=''):
    """
    Une notification par destinataire distinct (les None et doublons sont ignorés).
    Appelée dans la transaction de l'action : annulée avec elle en cas d'erreur.
    """
    vus, creees = set(), []
    for d in destinataires:
        if d is None or d.pk in vus or not d.is_active:
            continue
        vus.add(d.pk)
        creees.append(Notification(destinataire=d, evenement=evenement, titre=titre[:200], message=message,
                                   demande=demande, lien=lien or (f'/demandes/{demande.pk}' if demande else '')))
    Notification.objects.bulk_create(creees)
    return creees


def administrateurs():
    """Administrateurs et administrateurs des workflows actifs (alertes de paramétrage)."""
    User = get_user_model()
    return list(User.objects.filter(is_active=True).filter(
        groups__name__in=['super_admin', 'admin', 'admin_workflow']).distinct()) + \
        list(User.objects.filter(is_active=True, is_superuser=True))
