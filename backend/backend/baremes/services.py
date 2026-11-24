"""Lecture des barèmes à une date et copie figée pour une demande."""
from decimal import Decimal

from api.models import ParametreSysteme

from .models import ForfaitTransportHorsPays, PerDiem, TarifKilometrique, TarifTransportVille, TauxChange


def en_vigueur(modele, d, **cle):
    """Ligne applicable à la date d : la plus récente dont la date d'effet est ≤ d."""
    return modele.objects.filter(date_effet__lte=d, **cle).order_by('-date_effet', '-id').first()


def entree(ligne, libelle=''):
    """Copie figée d'une ligne de barème (stockée dans la demande)."""
    if ligne is None:
        return None
    montant = getattr(ligne, 'montant', None)
    return {'id': ligne.pk, 'modele': type(ligne).__name__, 'date_effet': ligne.date_effet.isoformat(),
            'montant': str(montant) if montant is not None else None, 'devise': getattr(ligne, 'devise', ''),
            'taux': str(ligne.taux) if isinstance(ligne, TauxChange) else None, 'libelle': libelle}


def devise_reference():
    return ParametreSysteme.charger().devise_reference


def taux(devise, d, ref=None):
    """Entrée de taux vers la devise de référence (taux 1 pour la devise de référence elle-même)."""
    ref = ref or devise_reference()
    devise = (devise or ref).upper()
    if devise == ref:
        return {'id': None, 'modele': 'TauxChange', 'date_effet': None, 'montant': None, 'devise': devise,
                'taux': '1', 'libelle': ''}
    return entree(en_vigueur(TauxChange, d, devise=devise))


def per_diem(type_mission, categorie, d):
    return entree(en_vigueur(PerDiem, d, type_mission=type_mission, categorie=categorie))


def tarif_km(type_mission, categorie, d):
    """Tarif propre à la catégorie s'il existe, sinon tarif commun à toutes les catégories."""
    ligne = None
    if categorie is not None:
        ligne = en_vigueur(TarifKilometrique, d, type_mission=type_mission, categorie=categorie)
    return entree(ligne or en_vigueur(TarifKilometrique, d, type_mission=type_mission, categorie__isnull=True))


def tarif_ville(ville, d):
    return entree(en_vigueur(TarifTransportVille, d, ville=ville)) if ville is not None else None


def forfait_hors_pays(d):
    return entree(en_vigueur(ForfaitTransportHorsPays, d))


def convertir(montant, entree_taux):
    """Montant en devise de référence (arrondi au centime)."""
    return (Decimal(str(montant)) * Decimal(entree_taux['taux'])).quantize(Decimal('0.01'))
