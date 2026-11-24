"""
Barèmes financiers datés (§3.6) : per diem, tarifs kilométriques, tarifs de
transport par ville, forfait de transport des missions hors pays, taux de
change. Une ligne n'est jamais modifiée : un changement = une nouvelle
ligne avec sa date d'effet (historique complet). Les demandes soumises
gardent une copie des barèmes appliqués (aucun effet rétroactif).
"""
from django.conf import settings
from django.db import models

TYPES_MISSION = [('locale', 'Mission locale'), ('hors_pays', 'Mission hors pays')]


class LigneBareme(models.Model):
    date_effet = models.DateField(db_index=True)
    motif = models.CharField(max_length=255, blank=True)
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    modifie_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-date_effet', '-id']


class PerDiem(LigneBareme):
    type_mission = models.CharField(max_length=10, choices=TYPES_MISSION)
    categorie = models.ForeignKey('api.Categoriesalarie', on_delete=models.PROTECT, related_name='per_diems')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    devise = models.CharField(max_length=3)

    CLE = ('type_mission', 'categorie')


class TarifKilometrique(LigneBareme):
    """Tarif par km (véhicule personnel). Catégorie vide = toutes les catégories."""
    type_mission = models.CharField(max_length=10, choices=TYPES_MISSION, default='locale')
    categorie = models.ForeignKey('api.Categoriesalarie', on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='tarifs_km')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    devise = models.CharField(max_length=3)

    CLE = ('type_mission', 'categorie')


class TarifTransportVille(LigneBareme):
    """Transport sans véhicule personnel, aller-retour inclus, même tarif pour toutes les catégories."""
    ville = models.ForeignKey('missions.Ville', on_delete=models.PROTECT, related_name='tarifs_transport')
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    devise = models.CharField(max_length=3)

    CLE = ('ville',)


class ForfaitTransportHorsPays(LigneBareme):
    """Trajet vers l'aéroport des missions hors pays."""
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    devise = models.CharField(max_length=3)

    CLE = ()


class TauxChange(LigneBareme):
    """1 unité de `devise` = `taux` unités de la devise de référence."""
    devise = models.CharField(max_length=3)
    taux = models.DecimalField(max_digits=18, decimal_places=6)

    CLE = ('devise',)
