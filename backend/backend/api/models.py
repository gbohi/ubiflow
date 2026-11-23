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


class Service(BaseModel):
    """Département (le nom technique « Service » est conservé pour l'API)."""
    libelle_service = models.CharField(max_length=255)


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
