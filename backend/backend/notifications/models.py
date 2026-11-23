from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Notification dans l'application (push et e-mail viendront s'y ajouter au lot 6)."""
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
