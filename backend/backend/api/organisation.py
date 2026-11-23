"""
Règles de l'organisation, toutes évaluées à une date donnée :
affectations en cours, titulaires des responsabilités, responsable d'un
département, N+1 et N+2 d'un collaborateur.

Ces fonctions sont la seule source de vérité : l'API, l'import Excel et,
plus tard, le moteur de workflow les appellent (aucune règle dans les vues).
"""
from dataclasses import dataclass, field
from datetime import date as date_type, datetime

from django.db.models import Q
from django.utils import timezone

from .models import (
    AffectationHierarchique, AffectationResponsabilite, Responsabilite, SituationVehicule,
    User, UserAgence, UserCategoriesalarie, UserPoste, UserService,
)


def date_du_jour():
    return timezone.localdate()


def normaliser_date(d):
    """date, datetime ou chaîne AAAA-MM-JJ → date (aujourd'hui si vide)."""
    if d in (None, ''):
        return date_du_jour()
    if isinstance(d, datetime):
        return timezone.localtime(d).date() if timezone.is_aware(d) else d.date()
    if isinstance(d, date_type):
        return d
    return date_type.fromisoformat(str(d)[:10])


# ── Lignes datées ──────────────────────────────────────────────

def filtre_en_cours(d, horodate=False):
    """
    Q des lignes actives à la date d (date_fin vide = en cours).
    horodate=True pour les affectations dont les dates sont des DateTimeField.
    """
    if horodate:
        return Q(date_debut__date__lte=d) & (Q(date_fin__isnull=True) | Q(date_fin__date__gte=d))
    return Q(date_debut__lte=d) & (Q(date_fin__isnull=True) | Q(date_fin__gte=d))


_AFFECTATIONS = {
    # cle : (modèle, champ, dates horodatées)
    'departement': (UserService, 'service', True),
    'agence':      (UserAgence, 'agence', True),
    'poste':       (UserPoste, 'poste', True),
    'categorie':   (UserCategoriesalarie, 'categoriesalarie', True),
}


def affectation_en_cours(user, cle, d=None):
    """Ligne d'affectation (département, agence, poste, catégorie) active à la date d."""
    modele, champ, horodate = _AFFECTATIONS[cle]
    d = normaliser_date(d)
    return (modele.objects.filter(user=user).filter(filtre_en_cours(d, horodate))
            .select_related(champ).order_by('-date_debut', '-id').first())


def valeur_en_cours(user, cle, d=None):
    ligne = affectation_en_cours(user, cle, d)
    return getattr(ligne, _AFFECTATIONS[cle][1]) if ligne else None


def departement_de(user, d=None):
    return valeur_en_cours(user, 'departement', d)


def possede_vehicule(user, d=None):
    """True / False selon la situation en cours, None si non renseignée."""
    d = normaliser_date(d)
    ligne = (SituationVehicule.objects.filter(user=user).filter(filtre_en_cours(d))
             .order_by('-date_debut', '-id').first())
    return ligne.possede_vehicule if ligne else None


# ── Responsabilités ────────────────────────────────────────────

def _responsabilite(code_ou_objet):
    if isinstance(code_ou_objet, Responsabilite):
        return code_ou_objet
    return Responsabilite.objects.filter(code=code_ou_objet).first()


def titulaires(responsabilite, d=None, departement=None, agence=None):
    """
    Collaborateurs actifs titulaires de la responsabilité à la date d,
    sur le périmètre demandé (département ou agence pour les responsabilités
    à portée limitée). Triés par nom.
    """
    resp = _responsabilite(responsabilite)
    if resp is None or not resp.actif:
        return []
    d = normaliser_date(d)
    qs = (AffectationResponsabilite.objects.filter(responsabilite=resp).filter(filtre_en_cours(d))
          .filter(user__is_active=True).select_related('user'))
    if resp.portee == Responsabilite.PORTEE_DEPARTEMENT:
        if departement is None:
            return []
        qs = qs.filter(departement=departement)
    elif resp.portee == Responsabilite.PORTEE_AGENCE:
        if agence is None:
            return []
        qs = qs.filter(agence=agence)
    users = {a.user_id: a.user for a in qs}
    return sorted(users.values(), key=lambda u: (u.nom.lower(), u.prenom.lower(), u.pk))


def responsable_departement(departement, d=None):
    """Responsable du département à la date d (ou None)."""
    resp = titulaires(Responsabilite.CODE_RESP_DEPARTEMENT, d, departement=departement)
    return resp[0] if resp else None


def responsabilites_de(user, d=None):
    d = normaliser_date(d)
    return list(AffectationResponsabilite.objects.filter(user=user).filter(filtre_en_cours(d))
                .select_related('responsabilite', 'departement', 'agence'))


# ── N+1 / N+2 ──────────────────────────────────────────────────

@dataclass
class ResolutionN1:
    """Résultat de la recherche du N+1 (responsable None = introuvable)."""
    responsable: User | None
    source: str                    # designe | departement | departement_parent | introuvable
    message: str
    affectation: AffectationHierarchique | None = None
    departement: object = None     # département dont le responsable a été retenu
    chemin: list = field(default_factory=list)

    @property
    def trouve(self):
        return self.responsable is not None


def affectation_hierarchique_en_cours(user, d=None):
    d = normaliser_date(d)
    return (AffectationHierarchique.objects.filter(user=user).filter(filtre_en_cours(d))
            .select_related('responsable').order_by('-date_debut', '-id').first())


def n_plus_1(user, d=None):
    """
    N+1 du collaborateur à la date d :
      1. affectation « personne désignée » en cours → cette personne (si active) ;
      2. sinon responsable de son département ;
      3. s'il est lui-même ce responsable, ou si le département n'a pas de
         responsable : responsable du département parent, en remontant ;
      4. sinon introuvable.
    """
    d = normaliser_date(d)
    aff = affectation_hierarchique_en_cours(user, d)
    if aff and aff.mode == AffectationHierarchique.MODE_DESIGNE:
        if aff.responsable and aff.responsable.is_active:
            return ResolutionN1(aff.responsable, 'designe', 'N+1 désigné', aff)
        return ResolutionN1(None, 'introuvable',
                            "Le N+1 désigné n'est plus actif : une nouvelle affectation est nécessaire.", aff)

    dept = departement_de(user, d)
    if dept is None:
        return ResolutionN1(None, 'introuvable',
                            "Aucun département à cette date : impossible de déterminer le N+1.", aff)

    chemin = []
    for niveau, candidat_dept in enumerate([dept, *dept.ancetres()]):
        chemin.append(candidat_dept.libelle_service)
        resp = responsable_departement(candidat_dept, d)
        if resp is not None and resp.pk != user.pk:
            source = 'departement' if niveau == 0 else 'departement_parent'
            libelle = (f"Responsable du département {candidat_dept.libelle_service}" if niveau == 0
                       else f"Responsable du département parent {candidat_dept.libelle_service}")
            return ResolutionN1(resp, source, libelle, aff, candidat_dept, chemin)
    return ResolutionN1(None, 'introuvable',
                        "Aucun responsable trouvé dans le département ni ses départements parents.",
                        aff, None, chemin)


def n_plus_2(user, d=None):
    premier = n_plus_1(user, d)
    if not premier.trouve:
        return premier
    second = n_plus_1(premier.responsable, d)
    if second.trouve and second.responsable.pk == user.pk:
        return ResolutionN1(None, 'introuvable', "Le N+2 serait le collaborateur lui-même.", second.affectation)
    return second


# ── Vue d'ensemble ─────────────────────────────────────────────

def _personne(u):
    if u is None:
        return None
    return {'id': u.pk, 'matricule': u.username, 'nom': u.nom, 'prenom': u.prenom,
            'nom_complet': f"{u.nom} {u.prenom}".strip() or u.username}


def _resolution(r):
    return {'personne': _personne(r.responsable), 'source': r.source, 'message': r.message,
            'departement': r.departement.libelle_service if r.departement else None,
            'mode': r.affectation.mode if r.affectation else AffectationHierarchique.MODE_AUTOMATIQUE,
            'exceptionnelle': bool(r.affectation and r.affectation.exceptionnelle)}


def organisation_de(user, d=None):
    """Situation organisationnelle complète du collaborateur à la date d."""
    d = normaliser_date(d)
    dept = departement_de(user, d)
    agence = valeur_en_cours(user, 'agence', d)
    poste = valeur_en_cours(user, 'poste', d)
    categorie = valeur_en_cours(user, 'categorie', d)
    return {
        'date': d.isoformat(),
        'collaborateur': _personne(user),
        'statut': user.statut.libelle_statut if user.statut_id else None,
        'departement': {'id': dept.pk, 'libelle': dept.libelle_service} if dept else None,
        'agence': {'id': agence.pk, 'libelle': agence.nom_agence} if agence else None,
        'poste': {'id': poste.pk, 'libelle': poste.libelle,
                  'fonction': poste.fonction.libelle if poste.fonction_id else None} if poste else None,
        'categorie': {'id': categorie.pk, 'libelle': categorie.libelle} if categorie else None,
        'possede_vehicule': possede_vehicule(user, d),
        'n_plus_1': _resolution(n_plus_1(user, d)),
        'n_plus_2': _resolution(n_plus_2(user, d)),
        'responsabilites': [
            {'id': a.pk, 'code': a.responsabilite.code, 'libelle': a.responsabilite.libelle,
             'departement': a.departement.libelle_service if a.departement_id else None,
             'agence': a.agence.nom_agence if a.agence_id else None,
             'date_debut': a.date_debut.isoformat(),
             'date_fin': a.date_fin.isoformat() if a.date_fin else None}
            for a in responsabilites_de(user, d)
        ],
    }
