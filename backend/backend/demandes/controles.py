"""
Contrôles d'alerte calculés à chaque soumission (décisions 8, 9 et 10) : ils
ne bloquent pas, ils sont signalés aux valideurs et à la comptabilité.
"""
from django.utils import timezone

from .models import Demande, StatutDemande

STATUTS_IGNORES = (StatutDemande.BROUILLON, StatutDemande.REJETEE, StatutDemande.ANNULEE)
CHAMPS_TIERS = ('client', 'beneficiaire', 'fournisseur')


def _periode(demande):
    from missions.calcul import _date_heure
    m = (demande.donnees or {}).get('mission') or {}
    try:
        return (timezone.localtime(_date_heure(m['depart_le'])).date(),
                timezone.localtime(_date_heure(m['retour_le'])).date())
    except (KeyError, ValueError, TypeError):
        return None


def alertes(demande):
    resultat = []
    autres = Demande.objects.filter(demandeur=demande.demandeur).exclude(pk=demande.pk).exclude(statut__in=STATUTS_IGNORES)

    if demande.type_demande.famille == 'mission':
        p = _periode(demande)
        if p:
            # 9 — mission déjà effectuée (régularisation)
            if p[1] < timezone.localdate():
                resultat.append({'code': 'regularisation', 'message': f"Mission déjà effectuée (retour le {p[1]:%d/%m/%Y}) : "
                                                                      "demande de régularisation."})
            # 8 — chevauchement avec une autre mission du collaborateur
            for autre in autres.filter(type_demande__famille='mission').select_related('type_demande'):
                q = _periode(autre)
                if q and q[0] <= p[1] and p[0] <= q[1]:
                    resultat.append({'code': 'chevauchement', 'demande': autre.pk, 'reference': autre.reference,
                                     'message': f"Dates qui se chevauchent avec la mission {autre.reference} "
                                                f"(du {q[0]:%d/%m/%Y} au {q[1]:%d/%m/%Y})."})
        return resultat

    # 10 — doublon probable : même type, même montant, et même date ou même tiers (ou moins de 30 jours d'écart)
    if demande.montant_demande:
        champs = list(demande.type_demande.champs.filter(actif=True))
        dates = [c.code for c in champs if c.nature in ('date', 'datetime')]
        tiers = [c.code for c in champs if c.code in CHAMPS_TIERS]
        d = demande.donnees or {}
        for autre in autres.filter(type_demande=demande.type_demande, montant_demande=demande.montant_demande):
            a = autre.donnees or {}
            meme_date = any(d.get(c) and str(d.get(c))[:10] == str(a.get(c) or '')[:10] for c in dates)
            meme_tiers = any(d.get(c) and str(d.get(c)).strip().lower() == str(a.get(c) or '').strip().lower() for c in tiers)
            recente = not dates and not tiers and abs((timezone.now() - (autre.soumise_le or autre.created_at)).days) <= 30
            if meme_date or meme_tiers or recente:
                raison = 'même date' if meme_date else 'même tiers' if meme_tiers else 'moins de 30 jours d\'écart'
                resultat.append({'code': 'doublon', 'demande': autre.pk, 'reference': autre.reference,
                                 'message': f"Doublon possible avec {autre.reference} ({autre.get_statut_display().lower()}) : "
                                            f"même montant, {raison}."})
    return resultat
