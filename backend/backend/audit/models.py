from django.conf import settings
from django.db import models


class JournalActivite(models.Model):
    """Journal des opérations, en ajout seul : jamais modifié ni supprimé par l'application."""
    horodatage = models.DateTimeField(auto_now_add=True, db_index=True)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                               related_name='journal_actions')
    pour_compte_de = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name='journal_pour_compte')
    action = models.CharField(max_length=60, db_index=True)
    objet_type = models.CharField(max_length=60, db_index=True)
    objet_id = models.CharField(max_length=40, blank=True)
    objet_libelle = models.CharField(max_length=255, blank=True)
    avant = models.JSONField(null=True, blank=True)
    apres = models.JSONField(null=True, blank=True)
    motif = models.TextField(blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    agent = models.CharField(max_length=255, blank=True)
    canal = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ['-horodatage', '-id']
