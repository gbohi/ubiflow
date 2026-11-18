"""
Statistiques complémentaires (page Statistiques UbiPharm, statistiques du
prestataire, rapport mensuel) :
  - desserts et suppléments : part des repas avec dessert, desserts préférés,
    coût des desserts offerts ;
  - participation : employés qui commandent / effectif de l'agence, repas
    par employé, employés qui n'ont jamais commandé ;
  - affluence au comptoir : retraits par tranche de 15 minutes, heure de pointe ;
  - comptes repas : recharges et débits par mois, soldes, soldes bas,
    compte repas / retenue sur salaire dans le temps ;
  - comparaison des prestataires : note, taux de retrait, contestations,
    coût moyen d'un repas ;
  - contrôle du comptoir : contestations par mois, cause, agent ; badges perdus ;
  - jeux : parties, joueurs, gagnants, coût, repas des joueurs / non-joueurs.

GET /statistiques/complements/?debut=&fin=&agence=&typeequipe=  (gestionnaires, administrateurs)
"""
from collections import OrderedDict, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import facturation as fact
from .models import (
    AvisPlat, BadgeAcces, Commande, CompteRepas, ContestationRetrait, GainJeu, MouvementCompte, ParticipationJeu,
    Retrait, User, UserAgence,
)
from .permissions import IsGestionnaireRole

ACTIVES = ('en_attente', 'retiree')
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
        'novembre', 'décembre']


def _f(v):
    return float(v or 0)


def _pct(n, total):
    return round(n / total * 100, 1) if total else None


def _bornes_dt(debut, fin):
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(debut, time.min), tz),
            timezone.make_aware(datetime.combine(fin, time.max), tz))


def _mois(debut, fin):
    cles, d = [], debut.replace(day=1)
    while d <= fin:
        cles.append((d.year, d.month))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return cles


def _libelle_mois(a, m):
    return f"{MOIS[m - 1].capitalize()} {a}"


# ══════════════════════════════════════════════════════════════
# 1. Desserts et suppléments
# ══════════════════════════════════════════════════════════════

def desserts(qs, prestataire_id=None):
    repas = qs.filter(commande_principale__isnull=True, statut__in=ACTIVES)
    sups = qs.filter(commande_principale__isnull=False, statut__in=ACTIVES)
    nb_repas = repas.count()
    avec = repas.filter(supplements__statut__in=ACTIVES).distinct().count()
    lignes = list(sups.values('plat_id', 'plat__nom', 'plat__type_plat__famille_supplement__libelle')
                  .annotate(n=Count('id'), s=Count('id', filter=Q(statut='retiree'))).order_by('-n', 'plat__nom'))
    total = sum(l['n'] for l in lignes)
    lp = [l for l in fact.lignes_prestataires(sups)
          if prestataire_id is None or (l['prestataire'] and l['prestataire'].id == prestataire_id)]
    cout = sum((l['montant'] or Decimal('0') for l in lp), Decimal('0'))
    cout_offerts = sum((l['montant'] or Decimal('0') for l in lp if l.get('offert')), Decimal('0'))
    return {
        'nb_repas': nb_repas, 'repas_avec_dessert': avec, 'part_avec_dessert': _pct(avec, nb_repas),
        'nb_desserts': total, 'cout': _f(cout), 'cout_offerts': _f(cout_offerts),
        'par_dessert': [{'plat_id': l['plat_id'], 'plat': l['plat__nom'],
                         'famille': l['plat__type_plat__famille_supplement__libelle'] or '',
                         'choisis': l['n'], 'servis': l['s'], 'part': _pct(l['n'], total)} for l in lignes],
        'prefere': lignes[0]['plat__nom'] if lignes else None,
    }


# ══════════════════════════════════════════════════════════════
# 2. Participation
# ══════════════════════════════════════════════════════════════

def effectifs(agence_ids=None, a_date=None):
    """{agence_id: {user_ids}} : employés actifs (rôle employé) rattachés à la date."""
    moment = timezone.make_aware(datetime.combine(a_date, time(12))) if a_date else timezone.now()
    qs = (UserAgence.objects.filter(date_debut__lte=moment, user__is_active=True, user__groups__name='employe')
          .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=moment)))
    if agence_ids is not None:
        qs = qs.filter(agence_id__in=agence_ids)
    resultat = defaultdict(set)
    for agence_id, nom, user_id in qs.values_list('agence_id', 'agence__nom_agence', 'user_id'):
        resultat[(agence_id, nom)].add(user_id)
    return resultat


def participation(qs, debut, fin, agence_ids=None):
    repas = qs.filter(commande_principale__isnull=True, statut__in=ACTIVES)
    eff = effectifs(agence_ids, min(fin, timezone.localdate()))
    tous = set().union(*eff.values()) if eff else set()
    commandeurs = set(repas.values_list('user_id', flat=True))
    jours_menu = repas.values('menu__date_menu').distinct().count()
    par_agence = []
    for (aid, nom), membres in sorted(eff.items(), key=lambda x: x[0][1]):
        r = repas.filter(user_id__in=membres)
        n = r.count()
        actifs = set(r.values_list('user_id', flat=True))
        jours = repas.filter(menu__agence_id=aid).values('menu__date_menu').distinct().count()
        par_agence.append({'agence_id': aid, 'agence': nom, 'effectif': len(membres), 'commandeurs': len(actifs),
                           'taux_participation': _pct(len(actifs), len(membres)), 'repas': n,
                           'repas_par_employe': round(n / len(actifs), 1) if actifs else 0,
                           'jours_service': jours,
                           'taux_journalier': _pct(n, len(membres) * jours) if jours else None})
    jamais_ids = sorted(tous - commandeurs)
    jamais = [{'user_id': u.id, 'nom': f"{u.nom} {u.prenom}".strip(), 'matricule': u.username}
              for u in User.objects.filter(id__in=jamais_ids[:200]).order_by('nom', 'prenom')]
    n_repas = repas.filter(user_id__in=tous).count()
    return {
        'effectif': len(tous), 'commandeurs': len(commandeurs & tous),
        'taux_participation': _pct(len(commandeurs & tous), len(tous)),
        'repas_par_employe': round(n_repas / len(commandeurs & tous), 1) if commandeurs & tous else 0,
        'jours_service': jours_menu,
        'par_agence': par_agence,
        'nb_jamais': len(jamais_ids), 'jamais': jamais,
    }


# ══════════════════════════════════════════════════════════════
# 3. Affluence au comptoir
# ══════════════════════════════════════════════════════════════

def affluence(retraits):
    """Retraits par tranche de 15 minutes (heure locale), moyenne par jour de service."""
    tranches = defaultdict(int)
    jours = set()
    for dt in retraits.values_list('date_retrait', flat=True):
        l = timezone.localtime(dt)
        tranches[(l.hour, l.minute // 15 * 15)] += 1
        jours.add(l.date())
    if not tranches:
        return {'tranches': [], 'pointe': None, 'nb_retraits': 0, 'jours': 0}
    debut, fin = min(tranches), max(tranches)
    liste, h, m = [], debut[0], debut[1]
    while (h, m) <= fin:
        n = tranches.get((h, m), 0)
        liste.append({'tranche': f"{h:02d}:{m:02d}", 'retraits': n, 'moyenne': round(n / len(jours), 1)})
        m += 15
        if m == 60:
            h, m = h + 1, 0
    pointe = max(liste, key=lambda t: t['retraits'])
    return {'tranches': liste, 'pointe': pointe, 'nb_retraits': sum(tranches.values()), 'jours': len(jours)}


# ══════════════════════════════════════════════════════════════
# 4. Comptes repas
# ══════════════════════════════════════════════════════════════

def comptes_repas(qs, debut, fin, user_ids=None, seuil=Decimal('2000')):
    d0, d1 = _bornes_dt(debut, fin)
    mv = MouvementCompte.objects.filter(created_at__range=(d0, d1))
    comptes = CompteRepas.objects.all()
    if user_ids is not None:
        mv = mv.filter(compte__user_id__in=user_ids)
        comptes = comptes.filter(user_id__in=user_ids)
    par_mois = OrderedDict(((a, m), {'annee': a, 'mois': m, 'libelle': _libelle_mois(a, m), 'recharges': 0.0,
                                     'nb_recharges': 0, 'debits': 0.0, 'repas_compte': 0, 'repas_retenue': 0})
                           for a, m in _mois(debut, fin))
    for t, dt, montant in mv.filter(type__in=('recharge', 'debit_repas')).values_list('type', 'created_at', 'montant'):
        l = timezone.localtime(dt)
        g = par_mois.get((l.year, l.month))
        if g is None:
            continue
        if t == 'recharge':
            g['recharges'] += _f(montant)
            g['nb_recharges'] += 1
        else:
            g['debits'] += abs(_f(montant))
    repas = qs.filter(commande_principale__isnull=True, statut__in=ACTIVES)
    for d, mode in repas.values_list('menu__date_menu', 'mode_paiement'):
        g = par_mois.get((d.year, d.month))
        if g is not None and mode in ('compte', 'retenue'):
            g['repas_' + mode] += 1
    agg = comptes.aggregate(total=Sum('solde'), n=Count('id'))
    bas = comptes.filter(solde__lt=seuil).select_related('user').order_by('solde')
    return {
        'solde_total': _f(agg['total']), 'nb_comptes': agg['n'] or 0,
        'recharges': sum(g['recharges'] for g in par_mois.values()),
        'nb_recharges': sum(g['nb_recharges'] for g in par_mois.values()),
        'debits': sum(g['debits'] for g in par_mois.values()),
        'seuil_bas': _f(seuil), 'nb_soldes_bas': bas.count(),
        'soldes_bas': [{'user_id': c.user_id, 'nom': f"{c.user.nom} {c.user.prenom}".strip(),
                        'matricule': c.user.username, 'solde': _f(c.solde)} for c in bas[:30]],
        'par_mois': list(par_mois.values()),
    }


# ══════════════════════════════════════════════════════════════
# 5. Comparaison des prestataires
# ══════════════════════════════════════════════════════════════

def prestataires(qs):
    lp = fact.lignes_prestataires(qs)
    groupes = {}
    for l in lp:
        p = l['prestataire']
        if p is None:
            continue
        g = groupes.setdefault(p.id, {'prestataire_id': p.id, 'prestataire': p.libelle, 'repas': 0, 'retires': 0,
                                      'non_retires': 0, 'montant_repas': Decimal('0'), 'supplements': 0,
                                      'agences': set()})
        g['agences'].add(l['agence_menu'])
        if l.get('supplement'):
            g['supplements'] += 1
            continue
        g['repas'] += 1
        g['retires' if l['statut'] == 'retiree' else 'non_retires'] += 1
        g['montant_repas'] += l['montant'] or Decimal('0')
    ids = list(groupes)
    notes = {r['commande__menu__prestataire_id']: r for r in AvisPlat.objects.filter(
        commande__in=qs, commande__menu__prestataire_id__in=ids)
        .values('commande__menu__prestataire_id').annotate(note=Avg('note'), n=Count('id'))}
    contest = dict(ContestationRetrait.objects.filter(commande__in=qs, menu__prestataire_id__in=ids)
                   .values('menu__prestataire_id').annotate(n=Count('id')).values_list('menu__prestataire_id', 'n'))
    resultat = []
    for pid, g in groupes.items():
        n = notes.get(pid)
        resultat.append({
            'prestataire_id': pid, 'prestataire': g['prestataire'], 'agences': sorted(g['agences']),
            'repas': g['repas'], 'supplements': g['supplements'],
            'taux_retrait': _pct(g['retires'], g['retires'] + g['non_retires']),
            'note': round(float(n['note']), 2) if n and n['note'] is not None else None,
            'nb_avis': n['n'] if n else 0,
            'contestations': contest.get(pid, 0),
            'taux_contestation': _pct(contest.get(pid, 0), g['retires']),
            'cout_moyen_repas': round(_f(g['montant_repas']) / g['repas']) if g['repas'] else None,
        })
    return sorted(resultat, key=lambda x: -x['repas'])


# ══════════════════════════════════════════════════════════════
# 6. Contrôle du comptoir
# ══════════════════════════════════════════════════════════════

def controle(debut, fin, menus_q=Q(), user_ids=None):
    d0, d1 = _bornes_dt(debut, fin)
    cq = ContestationRetrait.objects.filter(menus_q, created_at__range=(d0, d1))
    par_mois = OrderedDict(((a, m), {'annee': a, 'mois': m, 'libelle': _libelle_mois(a, m), 'contestations': 0,
                                     'acceptees': 0, 'badges_perdus': 0}) for a, m in _mois(debut, fin))
    for dt, statut in cq.values_list('created_at', 'statut'):
        l = timezone.localtime(dt)
        g = par_mois.get((l.year, l.month))
        if g:
            g['contestations'] += 1
            g['acceptees'] += statut == 'acceptee'
    libelles_causes = dict(ContestationRetrait.CAUSE_CHOICES)
    causes = [{'cause': r['cause'] or 'aucune',
               'libelle': libelles_causes.get(r['cause'], 'Non précisée' if r['statut'] == 'acceptee' else
                                              {'ouverte': 'En attente', 'rejetee': 'Rejetée'}.get(r['statut'], '—')),
               'statut': r['statut'], 'n': r['n']}
              for r in cq.values('cause', 'statut').annotate(n=Count('id')).order_by('-n')]
    agents = [{'agent_id': r['retrait_valide_par_id'],
               'agent': f"{r['retrait_valide_par__nom'] or ''} {r['retrait_valide_par__prenom'] or ''}".strip() or '—',
               'contestations': r['n'], 'acceptees': r['a']}
              for r in cq.exclude(retrait_valide_par__isnull=True)
              .values('retrait_valide_par_id', 'retrait_valide_par__nom', 'retrait_valide_par__prenom')
              .annotate(n=Count('id'), a=Count('id', filter=Q(statut='acceptee'))).order_by('-n')[:10]]
    badges = BadgeAcces.objects.filter(statut='perdu', fin_le__range=(d0, d1))
    if user_ids is not None:
        badges = badges.filter(user_id__in=user_ids)
    for dt in badges.values_list('fin_le', flat=True):
        l = timezone.localtime(dt)
        g = par_mois.get((l.year, l.month))
        if g:
            g['badges_perdus'] += 1
    return {'contestations': cq.count(), 'acceptees': cq.filter(statut='acceptee').count(),
            'ouvertes': cq.filter(statut='ouverte').count(), 'badges_perdus': badges.count(),
            'par_mois': list(par_mois.values()), 'causes': causes, 'agents': agents}


# ══════════════════════════════════════════════════════════════
# 7. Jeux
# ══════════════════════════════════════════════════════════════

def jeux(qs, debut, fin, user_ids=None):
    from .gains import couts_jeux
    d0, d1 = _bornes_dt(debut, fin)
    parts = ParticipationJeu.objects.filter(debut_le__range=(d0, d1))
    gains = GainJeu.objects.filter(created_at__range=(d0, d1))
    if user_ids is not None:
        parts = parts.filter(user_id__in=user_ids)
        gains = gains.filter(user_id__in=user_ids)
    par_mois = OrderedDict(((a, m), {'annee': a, 'mois': m, 'libelle': _libelle_mois(a, m), 'parties': 0,
                                     'joueurs': set(), 'gagnants': 0}) for a, m in _mois(debut, fin))
    for dt, u, lot in parts.values_list('debut_le', 'user_id', 'lot_id'):
        l = timezone.localtime(dt)
        g = par_mois.get((l.year, l.month))
        if g:
            g['parties'] += 1
            g['joueurs'].add(u)
            g['gagnants'] += lot is not None
    for dt in gains.values_list('created_at', flat=True):
        l = timezone.localtime(dt)
        g = par_mois.get((l.year, l.month))
        if g:
            g['gagnants'] += 1
    joueurs = set(parts.values_list('user_id', flat=True))
    repas = qs.filter(commande_principale__isnull=True, statut__in=ACTIVES)
    par_user = dict(repas.values('user_id').annotate(n=Count('id')).values_list('user_id', 'n'))
    rj = [par_user.get(u, 0) for u in joueurs]
    autres = [n for u, n in par_user.items() if u not in joueurs]
    cout = couts_jeux(debut, fin)['totaux']['total'] if user_ids is None else None
    return {
        'parties': parts.count(), 'joueurs': len(joueurs),
        'gagnants': parts.filter(lot__isnull=False).count() + gains.count(),
        'cout': cout,
        'repas_moyen_joueurs': round(sum(rj) / len(rj), 1) if rj else None,
        'repas_moyen_autres': round(sum(autres) / len(autres), 1) if autres else None,
        'par_mois': [{**{k: v for k, v in g.items() if k != 'joueurs'}, 'joueurs': len(g['joueurs'])}
                     for g in par_mois.values()],
    }


# ══════════════════════════════════════════════════════════════
# Vue
# ══════════════════════════════════════════════════════════════

def complements(per):
    """Toutes les statistiques complémentaires dans le périmètre (statistiques.Perimetre)."""
    qs = Commande.objects.filter(menu__date_menu__gte=per.debut, menu__date_menu__lte=per.fin)
    agence_ids = None
    if per.agence is not None:
        agence_ids = [per.agence]
    elif per.geres is not None:
        agence_ids = list(per.geres)
    if agence_ids is not None:
        qs = qs.filter(menu__agence_id__in=agence_ids)
    if per.typeequipe is not None:
        qs = qs.filter(menu__typeequipe_id=per.typeequipe)
    user_ids = None
    if agence_ids is not None:
        user_ids = set().union(*effectifs(agence_ids).values()) | set(qs.values_list('user_id', flat=True))
    menus_q = Q(menu__agence_id__in=agence_ids) if agence_ids is not None else Q()
    retraits = Retrait.objects.filter(menu__in=qs.values('menu_id'))
    return {
        'desserts': desserts(qs),
        'participation': participation(qs, per.debut, per.fin, agence_ids),
        'affluence': affluence(retraits),
        'comptes_repas': comptes_repas(qs, per.debut, per.fin, user_ids),
        'prestataires': prestataires(qs),
        'controle': controle(per.debut, per.fin, menus_q, user_ids),
        'jeux': jeux(qs, per.debut, per.fin, user_ids),
    }


class RapportMensuelView(APIView):
    """GET /statistiques/rapport-mensuel/?annee=&mois= : PDF du rapport mensuel (défaut : mois écoulé)."""
    permission_classes = [IsGestionnaireRole]

    def get(self, request):
        from django.http import HttpResponse
        from .models import ParametresSociete
        from .pdf_rapport import donnees_rapport, generer_rapport_mensuel
        from .permissions import agences_gerees
        auj = timezone.localdate()
        defaut_a, defaut_m = (auj.year, auj.month - 1) if auj.month > 1 else (auj.year - 1, 12)
        try:
            annee = int(request.query_params.get('annee') or defaut_a)
            mois = int(request.query_params.get('mois') or defaut_m)
            if not 1 <= mois <= 12:
                raise ValueError
        except ValueError:
            raise ValidationError("Paramètres annee et mois (1-12) attendus.")
        geres = agences_gerees(request.user)
        contenu = generer_rapport_mensuel(donnees_rapport(annee, mois, list(geres) if geres is not None else None),
                                          ParametresSociete.charger())
        r = HttpResponse(contenu, content_type='application/pdf')
        r['Content-Disposition'] = f'attachment; filename="rapport-cantine-{annee}-{mois:02d}.pdf"'
        return r


class ComplementsView(APIView):
    """GET /statistiques/complements/?debut=&fin=&agence=&typeequipe="""
    permission_classes = [IsGestionnaireRole]

    def get(self, request):
        from .statistiques import Perimetre
        per = Perimetre(request)
        if (per.fin - per.debut).days > 366:
            raise ValidationError("Période trop longue (un an au plus).")
        return Response({'debut': per.debut.isoformat(), 'fin': per.fin.isoformat(), **complements(per)})
