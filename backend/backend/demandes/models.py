"""
Socle générique des demandes : types de demande et leurs champs
paramétrables, demandes, versions de contenu, numérotation, commentaires,
pièces jointes. Voir docs/conception.md §3.4, §3.8 et §4.
"""
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


# ── Statuts ────────────────────────────────────────────────────

class StatutDemande(models.TextChoices):
    BROUILLON = 'brouillon', 'Brouillon'
    EN_VALIDATION = 'en_validation', 'En validation'
    A_CORRIGER = 'a_corriger', 'À corriger'
    REJETEE = 'rejetee', 'Rejetée'
    APPROUVEE = 'approuvee', 'Approuvée'
    EN_ATTENTE_CLOTURE = 'en_attente_cloture', 'En attente de clôture'
    CLOTUREE = 'cloturee', 'Clôturée'
    ANNULEE = 'annulee', 'Annulée'


STATUTS_FINAUX = {StatutDemande.REJETEE, StatutDemande.CLOTUREE, StatutDemande.ANNULEE}


class StatutFinancier(models.TextChoices):
    SANS_OBJET = 'sans_objet', 'Sans objet'
    A_PAYER = 'a_payer', 'À payer'
    PARTIELLEMENT_PAYEE = 'partiellement_payee', 'Partiellement payée'
    PAYEE = 'payee', 'Payée'
    REVERSEMENT_ATTENDU = 'reversement_attendu', 'Reversement attendu'
    SOLDEE = 'soldee', 'Soldée'


# ── Paramétrage ────────────────────────────────────────────────

class TypeDemande(models.Model):
    FAMILLES = [('simple', 'Simple (formulaire paramétrable)'), ('mission', 'Mission'),
                ('annulation', "Demande d'annulation")]
    MODES_CLOTURE = [('automatique', 'Automatique'), ('demandeur', 'Par le demandeur')]

    code = models.CharField(max_length=10, unique=True)
    libelle = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    famille = models.CharField(max_length=10, choices=FAMILLES, default='simple')
    actif = models.BooleanField(default=True)
    icone = models.CharField(max_length=40, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    prefixe_reference = models.CharField(max_length=10)
    avec_montant = models.BooleanField(default=True)
    paiement_fractionne_autorise = models.BooleanField(default=True)
    separation_approbation_paiement = models.BooleanField(default=False)
    mode_cloture = models.CharField(max_length=12, choices=MODES_CLOTURE, default='automatique')
    rapport_obligatoire = models.BooleanField(default=False)
    delai_cloture_jours = models.PositiveIntegerField(null=True, blank=True)
    # Statuts dans lesquels le demandeur peut annuler lui-même sa demande
    annulation_demandeur = models.JSONField(default=list, blank=True)
    # Paramètres propres à la famille (missions : {"type_mission": "locale" | "hors_pays"})
    parametres = models.JSONField(default=dict, blank=True)
    parent_requis = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='types_rattaches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordre', 'libelle']

    def __str__(self):
        return self.libelle


class ChampType(models.Model):
    """Champ du formulaire d'un type de demande (en plus de l'objet et du montant)."""
    NATURES = [
        ('texte', 'Texte'), ('texte_long', 'Texte long'), ('entier', 'Nombre entier'),
        ('montant', 'Montant'), ('date', 'Date'), ('datetime', 'Date et heure'),
        ('liste', 'Liste de choix'), ('booleen', 'Oui / non'), ('collaborateur', 'Collaborateur'),
    ]
    type_demande = models.ForeignKey(TypeDemande, on_delete=models.CASCADE, related_name='champs')
    code = models.SlugField(max_length=40)
    libelle = models.CharField(max_length=150)
    nature = models.CharField(max_length=15, choices=NATURES, default='texte')
    obligatoire = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    ordre = models.PositiveIntegerField(default=0)
    aide = models.CharField(max_length=255, blank=True)
    # Sa modification lors d'une correction impose la reprise du circuit au début
    sensible = models.BooleanField(default=False)
    utilisable_en_condition = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['ordre', 'id']
        unique_together = [('type_demande', 'code')]


class TypePiece(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    libelle = models.CharField(max_length=150)
    duree_conservation_ans = models.PositiveIntegerField(default=10)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class ExigencePiece(models.Model):
    MOMENTS = [('soumission', 'À la soumission'), ('etape', "À une étape de validation"),
               ('paiement', 'Au paiement'), ('cloture', 'À la clôture')]
    type_demande = models.ForeignKey(TypeDemande, on_delete=models.CASCADE, related_name='exigences')
    type_piece = models.ForeignKey(TypePiece, on_delete=models.PROTECT, related_name='exigences')
    moment = models.CharField(max_length=12, choices=MOMENTS, default='soumission')
    # Code de l'étape (stable d'une version de workflow à l'autre) si moment = etape
    etape_code = models.CharField(max_length=40, blank=True)
    obligatoire = models.BooleanField(default=True)

    class Meta:
        ordering = ['moment', 'id']


# ── Demandes ───────────────────────────────────────────────────

class Demande(models.Model):
    reference = models.CharField(max_length=30, unique=True, null=True, blank=True)
    type_demande = models.ForeignKey(TypeDemande, on_delete=models.PROTECT, related_name='demandes')
    demandeur = models.ForeignKey(User, on_delete=models.PROTECT, related_name='demandes')
    cree_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name='demandes_creees')
    statut = models.CharField(max_length=20, choices=StatutDemande.choices, default=StatutDemande.BROUILLON, db_index=True)
    statut_financier = models.CharField(max_length=20, choices=StatutFinancier.choices,
                                        default=StatutFinancier.SANS_OBJET)

    # Contenu de travail (brouillon / correction) ; figé dans VersionContenu à chaque soumission
    objet = models.CharField(max_length=255)
    montant_demande = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    devise = models.CharField(max_length=3, blank=True)
    donnees = models.JSONField(default=dict, blank=True)

    # Figés à la (première) soumission
    devise_reference = models.CharField(max_length=3, blank=True)
    montant_demande_ref = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    # Copie figée à la soumission : taux de change, barèmes des missions (§3.6)
    parametres_figes = models.JSONField(default=dict, blank=True)
    # Alertes non bloquantes calculées à la soumission (doublon, chevauchement, régularisation)
    alertes = models.JSONField(default=list, blank=True)
    departement = models.ForeignKey('api.Service', on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='demandes')
    agence = models.ForeignKey('api.Agence', on_delete=models.PROTECT, null=True, blank=True,
                               related_name='demandes')
    categorie = models.ForeignKey('api.Categoriesalarie', on_delete=models.PROTECT, null=True, blank=True,
                                  related_name='demandes')
    poste = models.ForeignKey('api.Poste', on_delete=models.PROTECT, null=True, blank=True, related_name='demandes')
    n_plus_1 = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='demandes_n_plus_1')
    version_workflow = models.ForeignKey('workflow.VersionWorkflow', on_delete=models.PROTECT, null=True,
                                         blank=True, related_name='demandes')
    version_courante = models.ForeignKey('VersionContenu', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='+')

    montant_approuve = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    montant_paye = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    montant_reverse = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    demande_parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='demandes_rattachees')
    origine_copie = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='copies')

    soumise_le = models.DateTimeField(null=True, blank=True)
    approuvee_le = models.DateTimeField(null=True, blank=True)
    cloturee_le = models.DateTimeField(null=True, blank=True)
    annulee_le = models.DateTimeField(null=True, blank=True)
    motif_annulation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.reference or f'Brouillon #{self.pk}'

    @property
    def solde(self):
        if self.montant_approuve is None:
            return None
        return self.montant_approuve - self.montant_paye


class VersionContenu(models.Model):
    """Contenu soumis (une version par soumission, plus les corrections des valideurs)."""
    ORIGINES = [('soumission', 'Soumission'), ('resoumission', 'Resoumission après correction'),
                ('correction_valideur', 'Correction par un valideur')]
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name='versions')
    numero = models.PositiveIntegerField()
    origine = models.CharField(max_length=20, choices=ORIGINES, default='soumission')
    objet = models.CharField(max_length=255)
    montant_demande = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    devise = models.CharField(max_length=3, blank=True)
    donnees = models.JSONField(default=dict, blank=True)
    calcul = models.JSONField(default=dict, blank=True)
    motif_modification = models.TextField(blank=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['numero']
        unique_together = [('demande', 'numero')]


class CompteurReference(models.Model):
    """Dernier numéro attribué par type et par année (numérotation sans trou)."""
    type_demande = models.ForeignKey(TypeDemande, on_delete=models.CASCADE, related_name='compteurs')
    annee = models.PositiveIntegerField()
    dernier_numero = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('type_demande', 'annee')]


class Commentaire(models.Model):
    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name='commentaires')
    auteur = models.ForeignKey(User, on_delete=models.PROTECT, related_name='commentaires_demandes')
    texte = models.TextField()
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creee_le', 'id']


def chemin_document(instance, nom):
    from django.utils import timezone
    import uuid
    extension = nom.rsplit('.', 1)[-1].lower() if '.' in nom else 'bin'
    return f"documents/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{extension}"


class Document(models.Model):
    demande = models.ForeignKey(Demande, on_delete=models.PROTECT, related_name='documents')
    type_piece = models.ForeignKey(TypePiece, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='documents')
    fichier = models.FileField(upload_to=chemin_document)
    nom_origine = models.CharField(max_length=255)
    taille = models.PositiveIntegerField()
    empreinte = models.CharField(max_length=64)
    version_contenu = models.ForeignKey(VersionContenu, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='documents')
    ajoute_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name='documents_ajoutes')
    ajoute_le = models.DateTimeField(auto_now_add=True)
    remplace = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='remplacants')
    retire = models.BooleanField(default=False)
    retire_le = models.DateTimeField(null=True, blank=True)
    retire_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    motif_retrait = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['ajoute_le', 'id']
