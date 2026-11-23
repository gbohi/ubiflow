"""
Moteur de workflow : modèle paramétrable (versions, étapes, règles de
désignation) et exécution (instances, étapes, tâches, actions, délégations).
Voir docs/conception.md §3.3 et §5.

Le moteur ne connaît aucun type de demande particulier : il lit la demande
au travers de `demandes.contexte_conditions(demande)`.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# ── Paramétrage ────────────────────────────────────────────────

class VersionWorkflow(models.Model):
    """Circuit d'un type de demande. Une seule version publiée à la fois ; publiée = figée."""
    ETATS = [('brouillon', 'Brouillon'), ('publiee', 'Publiée'), ('archivee', 'Archivée')]
    REPRISES = [('debut', 'Reprise à la première étape'),
                ('etape_retour_autorisee', "Reprise à l'étape du retour si rien de sensible n'a changé")]

    type_demande = models.ForeignKey('demandes.TypeDemande', on_delete=models.PROTECT,
                                     related_name='versions_workflow')
    numero = models.PositiveIntegerField()
    etat = models.CharField(max_length=10, choices=ETATS, default='brouillon', db_index=True)
    commentaire_version = models.TextField(blank=True)
    reprise_apres_correction = models.CharField(max_length=25, choices=REPRISES, default='debut')
    publiee_le = models.DateTimeField(null=True, blank=True)
    publiee_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['type_demande', '-numero']
        unique_together = [('type_demande', 'numero')]

    def __str__(self):
        return f'{self.type_demande.code} v{self.numero}'

    @property
    def modifiable(self):
        return self.etat == 'brouillon'


class Etape(models.Model):
    MODES = [('sequentiel', 'Séquentiel'), ('parallele', 'Parallèle')]
    REGLES_PARALLELE = [('tous', 'Tous doivent approuver'), ('un_seul', 'Une approbation suffit'),
                        ('quorum', 'Quorum')]
    AUTO_VALIDATION = [('manuelle', 'Il valide lui-même (manuellement)'),
                       ('automatique', 'Approbation automatique'),
                       ('sauter', "L'étape est sautée"),
                       ('remonter', 'Confiée à son N+1')]
    MEME_VALIDEUR = [('approbation_automatique', 'Approbation automatique'),
                     ('validation_requise', 'Nouvelle validation exigée')]
    INTROUVABLE = [('bloquer', 'Bloquer la soumission'), ('sauter', "Sauter l'étape"),
                   ('secours', 'Valideur de secours')]
    ACTIONS = ['approuver', 'rejeter', 'retourner']

    version = models.ForeignKey(VersionWorkflow, on_delete=models.CASCADE, related_name='etapes')
    ordre = models.PositiveIntegerField(default=1)
    code = models.SlugField(max_length=40)
    libelle = models.CharField(max_length=150)
    active = models.BooleanField(default=True)
    condition = models.JSONField(null=True, blank=True)
    mode = models.CharField(max_length=12, choices=MODES, default='sequentiel')
    regle_parallele = models.CharField(max_length=10, choices=REGLES_PARALLELE, default='tous')
    quorum = models.PositiveIntegerField(null=True, blank=True)
    actions_autorisees = models.JSONField(default=list)
    # Champs que le valideur peut corriger (codes des champs du type, ou « montant_approuve »)
    champs_modifiables = models.JSONField(default=list, blank=True)
    auto_validation_demandeur = models.CharField(max_length=12, choices=AUTO_VALIDATION, default='manuelle')
    meme_valideur_deja_passe = models.CharField(max_length=25, choices=MEME_VALIDEUR,
                                                default='validation_requise')
    valideur_introuvable = models.CharField(max_length=10, choices=INTROUVABLE, default='bloquer')
    valideur_secours = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['ordre', 'id']

    def __str__(self):
        return self.libelle


class RegleDesignation(models.Model):
    MODES = [('responsabilite', 'Par responsabilité'), ('personne', 'Par personne'),
             ('relation', 'Par relation hiérarchique')]
    PERIMETRES = [('aucun', 'Aucun'), ('departement_demandeur', 'Département du demandeur'),
                  ('agence_demandeur', 'Agence du demandeur')]
    RELATIONS = [('n_plus_1', 'N+1 du demandeur'), ('n_plus_2', 'N+2 du demandeur'),
                 ('responsable_departement', 'Responsable du département du demandeur'),
                 ('responsable_departement_parent', 'Responsable du département parent')]

    etape = models.ForeignKey(Etape, on_delete=models.CASCADE, related_name='regles')
    ordre = models.PositiveIntegerField(default=1)
    mode = models.CharField(max_length=15, choices=MODES)
    responsabilite = models.ForeignKey('api.Responsabilite', on_delete=models.PROTECT, null=True, blank=True,
                                       related_name='regles_workflow')
    perimetre = models.CharField(max_length=25, choices=PERIMETRES, default='aucun')
    personne = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    relation = models.CharField(max_length=35, choices=RELATIONS, blank=True)

    class Meta:
        ordering = ['ordre', 'id']


# ── Exécution ──────────────────────────────────────────────────

class InstanceWorkflow(models.Model):
    """Un cycle de validation d'une demande (un nouveau cycle à chaque resoumission)."""
    ETATS = [('en_cours', 'En cours'), ('approuvee', 'Approuvée'), ('rejetee', 'Rejetée'),
             ('retournee', 'Retournée'), ('annulee', 'Annulée')]
    demande = models.ForeignKey('demandes.Demande', on_delete=models.CASCADE, related_name='instances')
    version = models.ForeignKey(VersionWorkflow, on_delete=models.PROTECT, related_name='instances')
    cycle = models.PositiveIntegerField(default=1)
    etat = models.CharField(max_length=10, choices=ETATS, default='en_cours')
    date_reference = models.DateField()
    plan = models.JSONField(default=list)
    etape_retour = models.ForeignKey(Etape, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    creee_le = models.DateTimeField(auto_now_add=True)
    terminee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['demande', 'cycle']
        unique_together = [('demande', 'cycle')]


class EtapeInstance(models.Model):
    ETATS = [('a_venir', 'À venir'), ('en_cours', 'En cours'), ('approuvee', 'Approuvée'),
             ('rejetee', 'Rejetée'), ('retournee', 'Retournée'), ('sautee', 'Sautée'), ('annulee', 'Annulée')]
    instance = models.ForeignKey(InstanceWorkflow, on_delete=models.CASCADE, related_name='etapes')
    etape = models.ForeignKey(Etape, on_delete=models.PROTECT, related_name='instances')
    ordre = models.PositiveIntegerField()
    etat = models.CharField(max_length=10, choices=ETATS, default='a_venir')
    ouverte_le = models.DateTimeField(null=True, blank=True)
    cloturee_le = models.DateTimeField(null=True, blank=True)
    motif_saut = models.CharField(max_length=255, blank=True)
    # Approbation reprise d'un cycle précédent (retour pour correction sans changement sensible)
    reprise = models.BooleanField(default=False)

    class Meta:
        ordering = ['instance', 'ordre']


class Tache(models.Model):
    ETATS = [('a_venir', 'À venir'), ('en_attente', 'En attente'), ('faite', 'Faite'), ('annulee', 'Annulée')]
    DECISIONS = [('approuvee', 'Approuvée'), ('rejetee', 'Rejetée'), ('retournee', 'Retournée')]
    etape_instance = models.ForeignKey(EtapeInstance, on_delete=models.CASCADE, related_name='taches')
    valideur = models.ForeignKey(User, on_delete=models.PROTECT, related_name='taches_validation')
    ordre = models.PositiveIntegerField(default=1)
    etat = models.CharField(max_length=10, choices=ETATS, default='en_attente', db_index=True)
    # Responsabilité au titre de laquelle le valideur a été désigné (périmètre des délégations)
    responsabilite = models.ForeignKey('api.Responsabilite', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='+')
    auto_validation = models.BooleanField(default=False)
    decision = models.CharField(max_length=10, choices=DECISIONS, blank=True)
    traitee_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    creee_le = models.DateTimeField(auto_now_add=True)
    ouverte_le = models.DateTimeField(null=True, blank=True)
    traitee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['etape_instance', 'ordre', 'id']


class Action(models.Model):
    """Journal du workflow d'une demande, en ajout seul."""
    TYPES = [
        ('creation', 'Création'), ('soumission', 'Soumission'), ('resoumission', 'Resoumission'),
        ('approbation', 'Approbation'), ('auto_approbation', 'Approbation automatique'),
        ('rejet', 'Rejet'), ('retour', 'Retour pour correction'), ('commentaire', 'Commentaire'),
        ('annulation', 'Annulation'), ('saut', 'Étape sautée'), ('reresolution', 'Valideurs mis à jour'),
        ('reaffectation', 'Réaffectation'), ('correction', 'Correction par un valideur'),
        ('approbation_finale', 'Demande approuvée'), ('duplication', 'Duplication'),
        ('document', 'Pièce jointe'),
    ]
    demande = models.ForeignKey('demandes.Demande', on_delete=models.CASCADE, related_name='actions')
    instance = models.ForeignKey(InstanceWorkflow, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='actions')
    etape_instance = models.ForeignKey(EtapeInstance, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='actions')
    tache = models.ForeignKey(Tache, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions')
    type = models.CharField(max_length=20, choices=TYPES)
    auteur_reel = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    pour_compte_de = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    delegation = models.ForeignKey('Delegation', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    motif = models.TextField(blank=True)
    donnees = models.JSONField(null=True, blank=True)
    auto_validation = models.BooleanField(default=False)
    canal = models.CharField(max_length=10, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['horodatage', 'id']


class Delegation(models.Model):
    delegant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delegations_donnees')
    delegataire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delegations_recues')
    date_debut = models.DateField()
    date_fin = models.DateField()
    motif = models.CharField(max_length=255, blank=True)
    # Vides = tous les types / toutes les responsabilités
    types_demande = models.ManyToManyField('demandes.TypeDemande', blank=True, related_name='delegations')
    responsabilites = models.ManyToManyField('api.Responsabilite', blank=True, related_name='delegations')
    revoquee = models.BooleanField(default=False)
    revoquee_le = models.DateTimeField(null=True, blank=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_debut', '-id']

    @property
    def etat(self):
        if self.revoquee:
            return 'revoquee'
        aujourdhui = timezone.localdate()
        if aujourdhui < self.date_debut:
            return 'planifiee'
        if aujourdhui > self.date_fin:
            return 'terminee'
        return 'active'
