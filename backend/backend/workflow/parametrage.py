"""Paramétrage des circuits (§5.1) : versions brouillon, copie, contrôles, publication, simulation."""
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from api.models import Responsabilite

from . import conditions, moteur
from .erreurs import ErreurMetier
from .models import Etape, VersionWorkflow


def nouvelle_version(type_demande, auteur, source=None):
    """Brouillon vide, ou copie de `source` (en général la version publiée)."""
    if VersionWorkflow.objects.filter(type_demande=type_demande, etat='brouillon').exists():
        raise ErreurMetier("Un brouillon existe déjà pour ce type de demande : modifiez-le ou supprimez-le.")
    with transaction.atomic():
        numero = (VersionWorkflow.objects.filter(type_demande=type_demande).aggregate(m=Max('numero'))['m'] or 0) + 1
        version = VersionWorkflow.objects.create(
            type_demande=type_demande, numero=numero, cree_par=auteur,
            reprise_apres_correction=source.reprise_apres_correction if source else 'debut')
        if source is not None:
            for etape in source.etapes.all().prefetch_related('regles'):
                regles = list(etape.regles.all())
                etape.pk, etape.version = None, version
                etape.save()
                for r in regles:
                    r.pk, r.etape = None, etape
                    r.save()
    return version


def controler(version):
    """Erreurs bloquant la publication (liste vide = publiable)."""
    erreurs = []
    etapes = list(version.etapes.prefetch_related('regles__responsabilite'))
    actives = [e for e in etapes if e.active]
    if not actives:
        erreurs.append('Le circuit doit contenir au moins une étape active.')
    codes = [e.code for e in etapes]
    if len(codes) != len(set(codes)):
        erreurs.append('Deux étapes ont le même code.')
    for e in etapes:
        nom = f"Étape « {e.libelle} »"
        regles = list(e.regles.all())
        if not regles:
            erreurs.append(f"{nom} : aucun valideur désigné.")
        for r in regles:
            if r.mode == 'responsabilite':
                if r.responsabilite is None:
                    erreurs.append(f"{nom} : responsabilité non choisie.")
                elif r.responsabilite.portee == Responsabilite.PORTEE_DEPARTEMENT and r.perimetre != 'departement_demandeur':
                    erreurs.append(f"{nom} : « {r.responsabilite.libelle} » porte sur un département, "
                                   "choisissez le périmètre « Département du demandeur ».")
                elif r.responsabilite.portee == Responsabilite.PORTEE_AGENCE and r.perimetre != 'agence_demandeur':
                    erreurs.append(f"{nom} : « {r.responsabilite.libelle} » porte sur une agence, "
                                   "choisissez le périmètre « Agence du demandeur ».")
            elif r.mode == 'personne' and r.personne is None:
                erreurs.append(f"{nom} : collaborateur non choisi.")
            elif r.mode == 'relation' and not r.relation:
                erreurs.append(f"{nom} : relation hiérarchique non choisie.")
        if e.mode == 'parallele' and e.regle_parallele == 'quorum' and not e.quorum:
            erreurs.append(f"{nom} : indiquez le quorum.")
        if e.valideur_introuvable == 'secours' and e.valideur_secours is None:
            erreurs.append(f"{nom} : choisissez le valideur de secours.")
        try:
            conditions.valider(e.condition, version.type_demande)
        except ErreurMetier as ex:
            erreurs.append(f"{nom} : {ex.detail[0] if isinstance(ex.detail, list) else ex.detail}")
        if 'approuver' not in (e.actions_autorisees or []):
            erreurs.append(f"{nom} : l'action « approuver » est obligatoire.")
    return erreurs


def publier(version, auteur, commentaire=''):
    if version.etat != 'brouillon':
        raise ErreurMetier('Seul un brouillon peut être publié.')
    erreurs = controler(version)
    if erreurs:
        raise ErreurMetier({'publication': erreurs})
    with transaction.atomic():
        VersionWorkflow.objects.filter(type_demande=version.type_demande, etat='publiee').update(etat='archivee')
        version.etat, version.publiee_le, version.publiee_par = 'publiee', timezone.now(), auteur
        if commentaire:
            version.commentaire_version = commentaire
        version.save()
    return version


class _DemandeSimulee:
    """Demande « en mémoire » pour la simulation (aucune écriture)."""

    def __init__(self, type_demande, demandeur, montant, donnees, d):
        from api import organisation as org
        self.type_demande, self.demandeur, self.donnees = type_demande, demandeur, donnees or {}
        self.demandeur_id = demandeur.pk
        self.montant_demande = self.montant_demande_ref = montant
        self.departement = org.departement_de(demandeur, d)
        self.departement_id = getattr(self.departement, 'pk', None)
        self.agence = org.valeur_en_cours(demandeur, 'agence', d)
        self.agence_id = getattr(self.agence, 'pk', None)
        self.categorie = org.valeur_en_cours(demandeur, 'categorie', d)
        self.categorie_id = getattr(self.categorie, 'pk', None)
        self.n_plus_1 = org.n_plus_1(demandeur, d).responsable


def simuler(version, demandeur, montant=None, donnees=None):
    """Plan de validation qui résulterait d'une demande de ce collaborateur avec ces valeurs."""
    from decimal import Decimal
    from demandes.services import contexte_conditions
    d = timezone.localdate()
    montant = Decimal(str(montant)) if montant not in (None, '') else None
    demande = _DemandeSimulee(version.type_demande, demandeur, montant, donnees, d)
    return {
        'demandeur': moteur._personne(demandeur),
        'n_plus_1': moteur._personne(demande.n_plus_1) if demande.n_plus_1 else None,
        'departement': demande.departement.libelle_service if demande.departement else None,
        'plan': moteur.calculer_plan(version, demande, d, contexte_conditions(demande)),
    }


def reordonner(version, ids):
    if not version.modifiable:
        raise ErreurMetier('Version publiée : dupliquez-la pour la modifier.')
    etapes = {e.pk: e for e in version.etapes.all()}
    if set(ids) != set(etapes):
        raise ErreurMetier("La liste doit contenir toutes les étapes de la version.")
    with transaction.atomic():
        for ordre, pk in enumerate(ids, start=1):
            Etape.objects.filter(pk=pk).update(ordre=ordre)
