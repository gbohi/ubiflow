"""
Trésorerie (§3.7, §8) : règlements d'une demande approuvée (fractionnés si le
type l'autorise) et reversements dus par le demandeur (annulation après
paiement, clôture avec dépenses réelles inférieures au montant payé).
Les montants sont exprimés dans la devise de la demande.
"""
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL

MODES_PAIEMENT = [('virement', 'Virement'), ('cheque', 'Chèque'), ('especes', 'Espèces'),
                  ('mobile_money', 'Mobile money'), ('autre', 'Autre')]


class Reglement(models.Model):
    demande = models.ForeignKey('demandes.Demande', on_delete=models.PROTECT, related_name='reglements')
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3)
    taux_change = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    montant_ref = models.DecimalField(max_digits=16, decimal_places=2)
    date_paiement = models.DateField()
    mode = models.CharField(max_length=15, choices=MODES_PAIEMENT)
    reference = models.CharField(max_length=100, blank=True)
    beneficiaire = models.CharField(max_length=255)
    justificatif = models.ForeignKey('demandes.Document', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')
    enregistre_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    enregistre_le = models.DateTimeField(auto_now_add=True)
    annule = models.BooleanField(default=False)
    annule_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    annule_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.TextField(blank=True)

    class Meta:
        ordering = ['date_paiement', 'id']

    def __str__(self):
        return f"Règlement {self.montant} {self.devise} — {self.demande}"


class Reversement(models.Model):
    ETATS = [('a_percevoir', 'À percevoir'), ('percu', 'Perçu'), ('abandonne', 'Abandonné')]
    ORIGINES = [('annulation', 'Annulation après paiement'), ('cloture', 'Clôture : dépenses inférieures au payé')]
    demande = models.ForeignKey('demandes.Demande', on_delete=models.PROTECT, related_name='reversements')
    montant_du = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3)
    origine = models.CharField(max_length=12, choices=ORIGINES)
    motif = models.TextField(blank=True)
    etat = models.CharField(max_length=12, choices=ETATS, default='a_percevoir', db_index=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    # Perception ou abandon
    percu_le = models.DateField(null=True, blank=True)
    mode = models.CharField(max_length=15, choices=MODES_PAIEMENT, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    justificatif = models.ForeignKey('demandes.Document', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')
    motif_abandon = models.TextField(blank=True)
    traite_par = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    traite_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['cree_le', 'id']

    def __str__(self):
        return f"Reversement {self.montant_du} {self.devise} — {self.demande}"
