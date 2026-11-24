from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Notification dans l'application ; e-mail et push en plus selon l'événement et les préférences (canaux.py)."""
    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name='notifications_ubiflow')
    evenement = models.CharField(max_length=40, db_index=True)
    demande = models.ForeignKey('demandes.Demande', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='notifications')
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    lien = models.CharField(max_length=255, blank=True)
    lue = models.BooleanField(default=False, db_index=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creee_le', '-id']


class PreferenceNotification(models.Model):
    """Choix d'un collaborateur : recevoir ou non un événement par e-mail / push (l'application reçoit tout)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='preferences_notification')
    evenement = models.CharField(max_length=40)
    email = models.BooleanField(default=True)
    push = models.BooleanField(default=True)

    class Meta:
        unique_together = [('user', 'evenement')]


class AppareilMobile(models.Model):
    """Jeton Firebase (FCM) d'un téléphone sur lequel l'application mobile est connectée."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appareils_mobiles')
    jeton = models.CharField(max_length=500, unique=True)
    plateforme = models.CharField(max_length=10, choices=[('android', 'Android'), ('ios', 'iOS')], default='android')
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    vu_le = models.DateTimeField(auto_now=True)
