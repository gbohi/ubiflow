"""
Extension « mission » du socle des demandes : saisie structurée
(`donnees['mission']`), calcul, figement des barèmes, lignes de calcul et
champs utilisables dans les conditions du workflow.
"""
from datetime import date
from decimal import Decimal

from django.utils import timezone

from api import organisation as org
from demandes.extensions import Extension
from workflow.erreurs import ErreurMetier

from . import calcul
from .models import LigneCalcul, Pays


def type_mission(type_demande):
    return (type_demande.parametres or {}).get('type_mission') or 'locale'


def _date_depart(mission, defaut):
    try:
        return timezone.localtime(calcul._date_heure(mission['depart_le'])).date()
    except (KeyError, ValueError, TypeError):
        return defaut


def determinants(mission):
    return {k: mission.get(k) for k in calcul.DETERMINANTS}


def baremes_pour(demandeur, tm, mission, d, figes=None):
    """
    Barèmes applicables : la copie figée si elle existe et qu'aucun champ
    déterminant n'a changé, sinon ceux du jour d. Renvoie (fig, recalcul).
    """
    if figes and figes.get('determinants') == determinants(mission):
        return calcul.completer_taux(dict(figes, taux=dict(figes['taux'])), mission,
                                     date.fromisoformat(figes['date'][:10])), False
    categorie = org.valeur_en_cours(demandeur, 'categorie', _date_depart(mission, d))
    fig = calcul.figer_baremes(tm, categorie, mission, bool(org.possede_vehicule(demandeur, d)), d)
    fig['determinants'] = determinants(mission)
    return fig, bool(figes)


class ExtensionMission(Extension):
    montant_calcule = True

    def valider(self, type_demande, donnees, complet):
        return {'mission': calcul.normaliser(type_mission(type_demande), donnees.get('mission'), complet)}

    def avant_soumission(self, demande, d, premiere):
        tm = type_mission(demande.type_demande)
        mission = demande.donnees.get('mission') or {}
        figes = None if premiere else (demande.parametres_figes or {}).get('missions')
        fig, recalcul = baremes_pour(demande.demandeur, tm, mission, d, figes)
        resultat = calcul.calculer(tm, mission, fig)
        if resultat['erreurs']:
            raise ErreurMetier({'calcul': resultat['erreurs']})
        total = Decimal(resultat['total_ref'])
        note = None
        if recalcul:
            ancien = (demande.version_courante.calcul or {}).get('total_ref') if demande.version_courante else None
            resultat['recalcul'] = {'ancien_total_ref': ancien, 'date_baremes': fig['date']}
            note = (f"Champ déterminant modifié : calcul refait aux barèmes du {calcul._date_fr(fig['date'][:10])}"
                    + (f" (total précédent {calcul._fmt(Decimal(ancien))} {fig['devise_reference']})." if ancien else "."))
        demande.parametres_figes = {**(demande.parametres_figes or {}), 'missions': fig}
        demande.devise = demande.devise_reference = fig['devise_reference']
        demande.montant_demande = demande.montant_demande_ref = total
        return resultat, note

    def apres_version(self, demande, version):
        LigneCalcul.objects.bulk_create([LigneCalcul(
            demande=demande, version_contenu=version, ordre=i, rubrique=l['rubrique'], libelle=l['libelle'][:255],
            base=l['base'], unite=l['unite'], tarif=l['tarif'], devise=l['devise'], taux_change=l['taux'],
            montant=l['montant'], montant_ref=l['montant_ref'], bareme_source=l['source'],
            signalement=(l['signalement'] or '')[:255]) for i, l in enumerate(version.calcul.get('lignes', []))])

    def contexte(self, demande):
        m = (demande.donnees or {}).get('mission') or {}
        pays = Pays.objects.filter(pk=m.get('pays_destination')).values_list('code_iso', flat=True).first()
        return {'mission.type_mission': type_mission(demande.type_demande), 'mission.pays_destination': pays,
                'mission.nombre_jours': m.get('nombre_jours'), 'mission.moyen_transport': m.get('moyen_transport'),
                'mission.ville_destination': m.get('ville_destination_libelle')}

    def champs_condition(self, type_demande):
        return [
            {'code': 'mission.nombre_jours', 'libelle': 'Mission : nombre de jours', 'nature': 'entier'},
            {'code': 'mission.pays_destination', 'libelle': 'Mission : pays de destination (code ISO, ex. FR)',
             'nature': 'texte'},
            {'code': 'mission.ville_destination', 'libelle': 'Mission : ville de destination', 'nature': 'texte'},
            {'code': 'mission.moyen_transport', 'libelle': 'Mission : moyen de transport', 'nature': 'liste',
             'options': list(calcul.MOYENS)},
        ]

    def modification_sensible(self, ancien, nouveau):
        a, n = (ancien or {}).get('mission') or {}, (nouveau or {}).get('mission') or {}
        return any(a.get(k) != n.get(k) for k in calcul.SENSIBLES)


def apercu(user, type_demande, mission, demande=None):
    """
    Récapitulatif en direct pendant la saisie (rien n'est enregistré). Une
    demande à corriger garde ses barèmes figés tant qu'aucun déterminant ne change.
    """
    tm = type_mission(type_demande)
    try:
        donnees = calcul.normaliser(tm, mission, complet=False)
    except ErreurMetier as e:
        detail = e.detail.get('mission', {}) if isinstance(e.detail, dict) else {}
        return {'lignes': [], 'total_ref': '0.00', 'erreurs': [str(v) for v in detail.values()],
                'signalements': [], 'champs': {k: str(v) for k, v in detail.items()}}
    figes = (demande.parametres_figes or {}).get('missions') if demande is not None and demande.reference else None
    demandeur = demande.demandeur if demande is not None else user
    fig, recalcul = baremes_pour(demandeur, tm, donnees, timezone.localdate(), figes)
    resultat = calcul.calculer(tm, donnees, fig)
    resultat['mission'] = donnees
    if recalcul:
        resultat['signalements'].insert(0, "Champ déterminant modifié : le calcul sera refait aux barèmes du jour.")
    return resultat
