"""
Missions (§3.5) : référentiel des lieux et distances, lignes de calcul figées.

Les informations saisies d'une mission (dates, destination, transport,
frais) sont stockées dans `Demande.donnees`, validées par ce module : elles
sont ainsi versionnées, dupliquées et comparées comme le contenu de tout
autre type de demande.
"""
from django.conf import settings
from django.db import models


class Pays(models.Model):
    code_iso = models.CharField(max_length=2, unique=True)
    libelle = models.CharField(max_length=100)
    devise_usuelle = models.CharField(max_length=3, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']
        verbose_name_plural = 'pays'

    def __str__(self):
        return self.libelle


class Ville(models.Model):
    libelle = models.CharField(max_length=100)
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name='villes')
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']
        unique_together = [('libelle', 'pays')]

    def __str__(self):
        return self.libelle


class Distance(models.Model):
    """Distance routière validée entre deux villes (symétrique : enregistrée une seule fois)."""
    ville_a = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name='+')
    ville_b = models.ForeignKey(Ville, on_delete=models.CASCADE, related_name='+')
    km = models.PositiveIntegerField()

    class Meta:
        unique_together = [('ville_a', 'ville_b')]

    def save(self, *args, **kwargs):
        if self.ville_a_id and self.ville_b_id and self.ville_a_id > self.ville_b_id:
            self.ville_a_id, self.ville_b_id = self.ville_b_id, self.ville_a_id
        super().save(*args, **kwargs)

    @classmethod
    def entre(cls, a, b):
        if not a or not b:
            return None
        a_id, b_id = sorted([getattr(a, 'pk', a), getattr(b, 'pk', b)])
        return cls.objects.filter(ville_a_id=a_id, ville_b_id=b_id).first()


class LigneCalcul(models.Model):
    """Récapitulatif financier figé d'une version soumise (une ligne par rubrique)."""
    RUBRIQUES = [('per_diem', 'Indemnités journalières'), ('transport', 'Transport'), ('visa', 'Frais de visa'),
                 ('aerien', 'Transport aérien'), ('hebergement', 'Hébergement'), ('autres', 'Autres frais')]
    demande = models.ForeignKey('demandes.Demande', on_delete=models.CASCADE, related_name='lignes_calcul')
    version_contenu = models.ForeignKey('demandes.VersionContenu', on_delete=models.CASCADE,
                                        related_name='lignes_calcul')
    ordre = models.PositiveIntegerField(default=0)
    rubrique = models.CharField(max_length=12, choices=RUBRIQUES)
    libelle = models.CharField(max_length=255)
    base = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unite = models.CharField(max_length=20, blank=True)
    tarif = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    devise = models.CharField(max_length=3)
    taux_change = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    montant_ref = models.DecimalField(max_digits=16, decimal_places=2)
    bareme_source = models.JSONField(null=True, blank=True)
    signalement = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['version_contenu', 'ordre', 'id']


class ClotureMission(models.Model):
    """
    Éléments de clôture d'une mission (§9, mode B) : dates réelles, dépenses réelles
    par rubrique de la note de frais, observations ; contrôle facultatif par un rôle.
    Montants en devise de référence.
    """
    ETATS = [('brouillon', 'En cours de saisie'), ('soumise', 'Soumise au contrôle'), ('retournee', 'Retournée'),
             ('validee', 'Validée')]
    RUBRIQUES = ['hotel', 'transport', 'telephone', 'divers', 'reception', 'detaxe', 'a_refacturer']
    demande = models.OneToOneField('demandes.Demande', on_delete=models.CASCADE, related_name='cloture')
    etat = models.CharField(max_length=10, choices=ETATS, default='brouillon')
    depart_reel = models.DateField(null=True, blank=True)
    retour_reel = models.DateField(null=True, blank=True)
    depenses = models.JSONField(default=dict, blank=True)  # {rubrique: "montant", divers_detail, a_refacturer_detail}
    observations = models.TextField(blank=True)
    calcul = models.JSONField(default=dict, blank=True)    # récapitulatif figé à la validation
    soumise_le = models.DateTimeField(null=True, blank=True)
    controlee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='+')
    controlee_le = models.DateTimeField(null=True, blank=True)
    motif_retour = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Clôture {self.demande}"
