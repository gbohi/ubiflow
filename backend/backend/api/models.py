from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models


class BaseModel(models.Model):
    """Champs d'audit communs : dates et auteurs de création / modification."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_created = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_created'
    )
    user_updated = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='%(class)s_updated'
    )

    class Meta:
        abstract = True


# ============================================================
# UTILISATEURS
# ============================================================

class User(AbstractUser):
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255)
    # contact sert à l'envoi du code SMS « mot de passe oublié »
    contact = models.CharField(max_length=255, blank=True)
    poste_telephone = models.CharField(max_length=255, blank=True)
    statut = models.ForeignKey('Statut', on_delete=models.PROTECT)
    last_logout = models.DateTimeField(null=True, blank=True)
    # Photo de profil (modifiable par l'utilisateur lui-même, web et mobile)
    photo = models.ImageField(upload_to='photos_profil/', null=True, blank=True,
                              validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_created = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        related_name='utilisateurs_crees'
    )
    user_updated = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        related_name='utilisateurs_modifies'
    )

    class Meta:
        db_table = 'users'


# ============================================================
# RÉFÉRENTIELS
# ============================================================

class Statut(BaseModel):
    """Statut d'un compte ou d'une affectation (actif, suspendu…)."""
    libelle_statut = models.CharField(max_length=255)


class Agence(BaseModel):
    nom_agence = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)


class Service(BaseModel):
    """
    Département (le nom technique « Service » est conservé pour l'API).
    Les départements forment un arbre : le N+1 d'un responsable de
    département est le responsable du département parent.
    """
    libelle_service = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                               related_name='sous_departements')

    def ancetres(self):
        """Départements parents, du plus proche au plus éloigné."""
        vus, courant = {self.pk}, self.parent
        while courant is not None and courant.pk not in vus:
            vus.add(courant.pk)
            yield courant
            courant = courant.parent


class Fonction(BaseModel):
    libelle = models.CharField(max_length=100)


class Categoriesalarie(BaseModel):
    libelle = models.CharField(max_length=100)


class Poste(BaseModel):
    libelle = models.CharField(max_length=100)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    fonction = models.ForeignKey(Fonction, on_delete=models.PROTECT)


# ============================================================
# AFFECTATIONS DES UTILISATEURS (historisées)
# ============================================================

class UserService(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.ForeignKey(Statut, on_delete=models.PROTECT)


class UserAgence(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    agence = models.ForeignKey(Agence, on_delete=models.PROTECT)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.ForeignKey(Statut, on_delete=models.PROTECT)


class UserPoste(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    poste = models.ForeignKey(Poste, on_delete=models.PROTECT)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.ForeignKey(Statut, on_delete=models.PROTECT)


class UserCategoriesalarie(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    categoriesalarie = models.ForeignKey(Categoriesalarie, on_delete=models.PROTECT)
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.ForeignKey(Statut, on_delete=models.PROTECT)


class SituationVehicule(BaseModel):
    """Possession d'un véhicule personnel (historisée) : sert au calcul du transport."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='situations_vehicule')
    possede_vehicule = models.BooleanField()
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    commentaire = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date_debut']


# ============================================================
# RESPONSABILITÉS ET HIÉRARCHIE
# ============================================================

class Responsabilite(BaseModel):
    """
    Rôle tenu dans les circuits de validation (DG, DAF, Chef comptable,
    Responsable de département…), distinct de la fonction RH.
    """
    PORTEE_GLOBALE = 'globale'
    PORTEE_DEPARTEMENT = 'departement'
    PORTEE_AGENCE = 'agence'
    PORTEES = [
        (PORTEE_GLOBALE, 'Toute l\'entreprise'),
        (PORTEE_DEPARTEMENT, 'Un département'),
        (PORTEE_AGENCE, 'Une agence'),
    ]
    # Responsabilités utilisées par les règles de l'application (non supprimables)
    CODE_RESP_DEPARTEMENT = 'RESP_DEPARTEMENT'

    code = models.CharField(max_length=40, unique=True)
    libelle = models.CharField(max_length=150)
    portee = models.CharField(max_length=20, choices=PORTEES, default=PORTEE_GLOBALE)
    # Plusieurs titulaires en même temps, sur le même périmètre
    multiple = models.BooleanField(default=False)
    systeme = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ['libelle']

    def __str__(self):
        return self.libelle


class AffectationResponsabilite(BaseModel):
    """Titulaire d'une responsabilité sur une période (et un périmètre)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='responsabilites')
    responsabilite = models.ForeignKey(Responsabilite, on_delete=models.PROTECT, related_name='affectations')
    departement = models.ForeignKey(Service, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='affectations_responsabilite')
    agence = models.ForeignKey(Agence, on_delete=models.PROTECT, null=True, blank=True,
                               related_name='affectations_responsabilite')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    motif = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date_debut']


class AffectationHierarchique(BaseModel):
    """
    Historique des N+1 d'un collaborateur.
    - automatique : N+1 = responsable de son département à la date considérée ;
    - designe : N+1 = la personne indiquée.
    """
    MODE_AUTOMATIQUE = 'automatique'
    MODE_DESIGNE = 'designe'
    MODES = [(MODE_AUTOMATIQUE, 'Responsable du département'), (MODE_DESIGNE, 'Personne désignée')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='affectations_hierarchiques')
    mode = models.CharField(max_length=20, choices=MODES, default=MODE_AUTOMATIQUE)
    responsable = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='collaborateurs_designes')
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    # Réaffectation exceptionnelle (administrateur) : motif obligatoire
    exceptionnelle = models.BooleanField(default=False)
    motif = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-date_debut']


# ============================================================
# IMPORT DES COLLABORATEURS (Excel)
# ============================================================

class ImportCollaborateurs(models.Model):
    fichier_nom = models.CharField(max_length=255)
    auteur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='imports_collaborateurs')
    cree_le = models.DateTimeField(auto_now_add=True)
    date_effet = models.DateField()
    simulation = models.BooleanField(default=False)
    nb_lignes = models.PositiveIntegerField(default=0)
    nb_crees = models.PositiveIntegerField(default=0)
    nb_mis_a_jour = models.PositiveIntegerField(default=0)
    nb_inchanges = models.PositiveIntegerField(default=0)
    nb_rejetes = models.PositiveIntegerField(default=0)
    # [{"ligne": 3, "matricule": "A12", "resultat": "cree|mis_a_jour|inchange|rejete",
    #   "messages": ["…"]}]
    rapport = models.JSONField(default=list)

    class Meta:
        ordering = ['-cree_le']


# ============================================================
# PARAMÈTRES SYSTÈME
# ============================================================

class ParametreSysteme(models.Model):
    """Réglages globaux (une seule ligne)."""
    devise_reference = models.CharField(max_length=3, default='XOF')
    taille_max_piece_mo = models.PositiveIntegerField(default=10)
    updated_at = models.DateTimeField(auto_now=True)
    user_updated = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    @classmethod
    def charger(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
