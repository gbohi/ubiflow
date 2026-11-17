"""
Indicateurs des plats et des montants (page Statistiques UbiPharm et
statistiques du prestataire).

Plats (plats principaux ; suppléments à part) : plat le plus / le moins
commandé, popularité (part des commandes), commandes par menu, préférences
par agence (part de chaque plat dans les commandes de l'agence), évolution
de la popularité des 5 plats les plus commandés (par mois, ou par semaine
sur une période de deux mois au plus).

Montants : facturé aux employés (UbiPharm seulement) et dû aux prestataires,
par mois, agence, plat, type de plat (desserts compris), mode de règlement
et prestataire — calculés par facturation.py (montants figés si clôturé).

Utilisé par :
  - GET /statistiques/indicateurs/                (gestionnaires, administrateurs)
  - GET /prestataire/statistiques/indicateurs/    (responsable du prestataire)
"""
from collections import OrderedDict, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from . import facturation as fact
from .models import Commande
from .permissions import IsGestionnaireRole

ACTIVES = ('en_attente', 'retiree')
MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
              'novembre', 'décembre']
LIBELLES_MODES = {'compte': 'Compte repas', 'caisse': 'Caisse', 'retenue': 'Retenue sur salaire',
                  'offert': 'Repas offerts'}


def _f(v):
    return float(v) if v is not None else 0.0


def _pct(n, total):
    return round(n / total * 100, 1) if total else 0.0


def _cle_periode(d, semaine):
    return d - timedelta(days=d.weekday()) if semaine else d.replace(day=1)


def _libelle_periode(d, semaine):
    return f"{d:%d/%m}" if semaine else f"{MOIS_COURTS[d.month - 1]} {d:%y}"


def _periodes(debut, fin, semaine):
    cles, d = [], _cle_periode(debut, semaine)
    while d <= fin:
        cles.append(d)
        d = d + timedelta(days=7) if semaine else (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return cles


def plats(qs, debut, fin):
    """Indicateurs des plats sur `qs` (commandes de la période, suppléments compris)."""
    repas = qs.filter(commande_principale__isnull=True, statut__in=ACTIVES)
    lignes = list(repas.values('plat_id', 'plat__nom', 'plat__type_plat__libelle')
                  .annotate(n=Count('id'), s=Count('id', filter=Q(statut='retiree')))
                  .order_by('-n', 'plat__nom'))
    total = sum(l['n'] for l in lignes)
    par_plat = [{'plat_id': l['plat_id'], 'plat': l['plat__nom'], 'type_plat': l['plat__type_plat__libelle'] or '',
                 'commandes': l['n'], 'servis': l['s'], 'popularite': _pct(l['n'], total)} for l in lignes]

    # Commandes par menu (les plus récents d'abord)
    menus = list(repas.values('menu_id', 'menu__date_menu', 'menu__agence__nom_agence', 'menu__typeequipe__libelle')
                 .annotate(n=Count('id'), s=Count('id', filter=Q(statut='retiree')))
                 .order_by('-menu__date_menu', 'menu__agence__nom_agence'))
    par_menu = [{'menu_id': m['menu_id'], 'date': m['menu__date_menu'].isoformat(),
                 'agence': m['menu__agence__nom_agence'] or '', 'equipe': m['menu__typeequipe__libelle'] or '',
                 'commandes': m['n'], 'servis': m['s']} for m in menus]

    # Préférences par agence : part de chaque plat (8 plus commandés) dans l'agence
    croise = defaultdict(lambda: defaultdict(int))
    tot_agence = defaultdict(int)
    for r in repas.values('plat__nom', 'menu__agence__nom_agence').annotate(n=Count('id')):
        ag = r['menu__agence__nom_agence'] or '—'
        croise[r['plat__nom']][ag] += r['n']
        tot_agence[ag] += r['n']
    agences = sorted(tot_agence, key=lambda a: (-tot_agence[a], a))
    preferences = {
        'agences': [{'agence': a, 'commandes': tot_agence[a]} for a in agences],
        'plats': [{'plat': p['plat'], 'commandes': p['commandes'],
                   'parts': {a: _pct(croise[p['plat']].get(a, 0), tot_agence[a]) for a in agences},
                   'nb': {a: croise[p['plat']].get(a, 0) for a in agences}} for p in par_plat[:8]],
    }

    # Évolution de la popularité des 5 plats les plus commandés
    semaine = (fin - debut).days <= 62
    cles = _periodes(debut, fin, semaine)
    top = [p['plat'] for p in par_plat[:5]]
    par_periode = defaultdict(lambda: defaultdict(int))
    tot_periode = defaultdict(int)
    for r in repas.values('plat__nom', 'menu__date_menu').annotate(n=Count('id')):
        k = _cle_periode(r['menu__date_menu'], semaine)
        tot_periode[k] += r['n']
        if r['plat__nom'] in top:
            par_periode[r['plat__nom']][k] += r['n']
    evolution = {
        'granularite': 'semaine' if semaine else 'mois',
        'periodes': [_libelle_periode(k, semaine) for k in cles],
        'series': [{'plat': p, 'parts': [_pct(par_periode[p].get(k, 0), tot_periode.get(k, 0)) for k in cles],
                    'commandes': [par_periode[p].get(k, 0) for k in cles]} for p in top],
    }

    nb_menus = len(par_menu)
    return {
        'kpis': {
            'nb_repas': total, 'nb_plats': len(par_plat), 'nb_menus': nb_menus,
            'moyenne_par_menu': round(total / nb_menus, 1) if nb_menus else 0,
            'plat_plus': par_plat[0] if par_plat else None,
            'plat_moins': par_plat[-1] if len(par_plat) > 1 else None,
            'nb_supplements': qs.filter(commande_principale__isnull=False, statut__in=ACTIVES).count(),
        },
        'par_plat': par_plat,
        'par_menu': par_menu[:120],
        'preferences': preferences,
        'evolution': evolution,
    }


def montants(qs, debut, fin, prestataire_id=None, avec_employes=True):
    """
    Montants de la période : dû aux prestataires (celui-ci seulement si
    prestataire_id) et, pour UbiPharm, facturé aux employés.
    """
    lp = [l for l in fact.lignes_prestataires(qs)
          if l['prestataire'] is not None and (prestataire_id is None or l['prestataire'].id == prestataire_id)]
    le = fact.lignes_facturation(qs.filter(commande_principale__isnull=True), inclure_offerts=True) \
        if avec_employes else []

    cles = _periodes(debut, fin, False)
    mois = OrderedDict((k, {'annee': k.year, 'mois': k.month, 'libelle': f"{MOIS_LONGS[k.month - 1].capitalize()} {k.year}",
                            'court': _libelle_periode(k, False), 'employes': Decimal('0'),
                            'prestataires': Decimal('0'), 'repas': 0, 'supplements': 0}) for k in cles)
    agences, plats_m, types, prest = (defaultdict(lambda: {'employes': Decimal('0'), 'prestataires': Decimal('0'),
                                                           'repas': 0, 'supplements': 0}) for _ in range(4))
    for l in lp:
        m = l['montant'] or Decimal('0')
        sup = bool(l.get('supplement'))
        k = l['date_menu'].replace(day=1)
        for g in (mois.get(k), agences[l['agence_menu'] or '—'], plats_m[l['plat']],
                  types[l.get('type_plat') or 'Tous types'], prest[l['prestataire'].libelle]):
            if g is None:
                continue
            g['prestataires'] += m
            g['supplements' if sup else 'repas'] += 1
    modes = defaultdict(lambda: {'montant': Decimal('0'), 'nb': 0})
    from .models import TypePlat
    libelles_types = dict(TypePlat.objects.values_list('id', 'libelle'))
    for l in le:
        m = l['montant'] or Decimal('0')
        k = l['date_menu'].replace(day=1)
        types_emp = libelles_types.get(l.get('type_plat_id')) or 'Tous types'
        for g in (mois.get(k), agences[l['agence_menu'] or '—'], plats_m[l['plat']], types[types_emp]):
            if g is not None:
                g['employes'] += m
        mode = 'offert' if l.get('offert') else (l.get('reglement') if l.get('reglement') in ('compte', 'caisse')
                                                 else l.get('mode_paiement') or 'retenue')
        if mode not in LIBELLES_MODES:
            mode = 'retenue'
        modes[mode]['montant'] += m
        modes[mode]['nb'] += 1

    def liste(d, cle):
        return sorted(({cle: k, 'employes': _f(v['employes']), 'prestataires': _f(v['prestataires']),
                        'repas': v['repas'], 'supplements': v['supplements']} for k, v in d.items()),
                      key=lambda x: (-(x['employes'] + x['prestataires']), x[cle]))

    resultat = {
        'total_prestataires': _f(sum((l['montant'] or Decimal('0') for l in lp), Decimal('0'))),
        'par_mois': [{**v, 'employes': _f(v['employes']), 'prestataires': _f(v['prestataires'])}
                     for v in mois.values()],
        'par_agence': liste(agences, 'agence'),
        'par_plat': liste(plats_m, 'plat')[:12],
        'par_type': liste(types, 'type_plat'),
        'par_prestataire': liste(prest, 'prestataire'),
    }
    if avec_employes:
        resultat['total_employes'] = _f(sum((l['montant'] or Decimal('0') for l in le), Decimal('0')))
        resultat['par_mode'] = [{'mode': k, 'libelle': LIBELLES_MODES[k], 'montant': _f(v['montant']), 'nb': v['nb']}
                                for k, v in sorted(modes.items(), key=lambda kv: -kv[1]['montant'])]
    else:
        for cle in ('par_mois', 'par_agence', 'par_plat', 'par_type', 'par_prestataire'):
            for x in resultat[cle]:
                x.pop('employes', None)
    return resultat


class IndicateursView(APIView):
    """GET /statistiques/indicateurs/?debut=&fin=&agence=&typeequipe= : plats et montants (UbiPharm)."""
    permission_classes = [IsGestionnaireRole]

    def get(self, request):
        from .statistiques import Perimetre
        per = Perimetre(request)
        if (per.fin - per.debut).days > 366:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Période trop longue (un an au plus).")
        qs = Commande.objects.filter(menu__date_menu__gte=per.debut, menu__date_menu__lte=per.fin)
        if per.agence is not None:
            qs = qs.filter(menu__agence_id=per.agence)
        elif per.geres is not None:
            qs = qs.filter(menu__agence_id__in=per.geres)
        if per.typeequipe is not None:
            qs = qs.filter(menu__typeequipe_id=per.typeequipe)
        return Response({'debut': per.debut.isoformat(), 'fin': per.fin.isoformat(),
                         **plats(qs, per.debut, per.fin), 'montants': montants(qs, per.debut, per.fin)})
