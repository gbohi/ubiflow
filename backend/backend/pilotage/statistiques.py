"""
Statistiques : huit tableaux thématiques (vue globale, missions, finances,
paiements, départements, circuits de validation, remboursements et frais
complémentaires, réceptions clients).

Chaque tableau = quelques indicateurs en tête, trois graphiques au plus, puis
un tableau détaillé (valeurs exactes, lien vers les demandes). Le format des
sections est celui des tableaux de bord (indicateurs.py), enrichi de types de
graphiques : courbe, anneau, colonnes empilées, barres empilées, entonnoir,
carte. Tous les tableaux acceptent les mêmes filtres (période, type, statut,
département, agence, catégorie, demandeur) ; période par défaut : l'année en cours.
Les montants sont en devise de référence (taux figés des demandes).
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.utils import timezone

from api import calendrier
from api.models import ParametreSysteme
from api.permissions import filtre_perimetre, get_roles, is_admin, is_admin_finances, is_comptable
from demandes.models import Demande, StatutDemande
from workflow import moteur
from workflow.erreurs import Interdit

from .indicateurs import (APPROUVEES, _ligne_demande, barres, colonnes, demandes, filtres, ind, libelle_mois,
                          mois_periode, ref, tableau)

THEMES = [
    ('global', 'Vue globale', 'ri-dashboard-line', 'Vue globale'),
    ('missions', 'Missions', 'ri-road-map-line', 'Missions'),
    ('finances', 'Finances et budget', 'ri-funds-line', 'Finances'),
    ('paiements', 'Paiements et comptabilité', 'ri-wallet-3-line', 'Paiements'),
    ('departements', 'Départements et services', 'ri-organization-chart', 'Départements'),
    ('circuits', 'Circuits et validations', 'ri-git-merge-line', 'Circuits'),
    ('remboursements', 'Remboursements et frais complémentaires', 'ri-refund-2-line', 'Remboursements'),
    ('receptions', 'Réceptions clients', 'ri-restaurant-line', 'Réceptions'),
]

# Statuts regroupés, dans l'ordre d'affichage (les couleurs suivent la clé, côté web)
GROUPES_STATUT = [
    ('en_validation', 'En validation', (StatutDemande.EN_VALIDATION,)),
    ('a_corriger', 'À corriger', (StatutDemande.A_CORRIGER,)),
    ('rejetee', 'Rejetées', (StatutDemande.REJETEE,)),
    ('approuvee', 'Approuvées', (StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE)),
    ('cloturee', 'Clôturées', (StatutDemande.CLOTUREE,)),
    ('annulee', 'Annulées', (StatutDemande.ANNULEE,)),
]
GROUPE_DE = {s: cle for cle, _, statuts in GROUPES_STATUT for s in statuts}

# Natures de dépense (finances) : regroupement des types de demande
NATURES = [('missions', 'Missions'), ('receptions', 'Réceptions clients'), ('paiements', 'Paiements'),
           ('remboursements', 'Remboursements')]
NATURE_DU_TYPE = {'MLO': 'missions', 'MHP': 'missions', 'FCM': 'missions', 'FRC': 'receptions',
                  'PAI': 'paiements', 'RMB': 'remboursements'}


def acces_statistiques(user):
    """Direction, contrôle, finances, comptabilité et administrateurs."""
    return bool(is_admin(user) or is_comptable(user) or is_admin_finances(user)
                or get_roles(user) & {'direction', 'controleur'})


# ═══════════════════════════════════════════════════════════════
# SECTIONS (graphiques supplémentaires)
# ═══════════════════════════════════════════════════════════════

def _s(v):
    return str(v) if isinstance(v, Decimal) else v


def courbe(cle, titre, mois, series, valeurs, unite='montant', aide=''):
    return {'cle': cle, 'titre': titre, 'type': 'courbe', 'unite': unite, 'aide': aide,
            'series': [{'cle': c, 'libelle': l} for c, l in series],
            'donnees': [{'libelle': libelle_mois(m), 'valeurs': {c: _s(valeurs[m].get(c, 0)) for c, _ in series}}
                        for m in mois]}


def anneau(cle, titre, parts, unite='nombre', palette='categorielle', limite=6, aide='', teintes=None):
    """
    parts : [(clé, libellé, valeur)] ; au-delà de `limite`, la fin est regroupée en « Autres ».
    teintes : {clé: rang} fixe de chaque entité, pour que sa couleur ne change pas d'un filtre à l'autre
    (la couleur suit l'entité, jamais son rang dans le classement).
    """
    parts = [p for p in parts if p[2]]
    if teintes is not None:
        parts.sort(key=lambda p: -p[2])
    if len(parts) > limite:
        parts = parts[:limite - 1] + [('autres', 'Autres', sum(p[2] for p in parts[limite - 1:]))]
    teintes = teintes or {}
    return {'cle': cle, 'titre': titre, 'type': 'anneau', 'unite': unite, 'palette': palette, 'aide': aide,
            'donnees': [{'cle': c, 'libelle': l or 'Non renseigné', 'valeur': _s(v),
                         **({'teinte': teintes[c] % 8} if c in teintes else {})} for c, l, v in parts]}


def _teintes_departements():
    from api.models import Service
    rangs = {s.libelle_service: i for i, s in enumerate(Service.objects.order_by('pk'))}
    rangs['Non renseigné'] = len(rangs)
    return rangs


def empilees(cle, titre, type_, categories, series, valeurs, unite='montant', palette='categorielle', aide=''):
    """Colonnes (type_='colonnes_empilees', catégories = mois) ou barres horizontales empilées."""
    return {'cle': cle, 'titre': titre, 'type': type_, 'unite': unite, 'palette': palette, 'aide': aide,
            'series': [{'cle': c, 'libelle': l} for c, l in series],
            'donnees': [{'libelle': lib, 'valeurs': {c: _s(valeurs[k].get(c, 0)) for c, _ in series}}
                        for k, lib in categories]}


def entonnoir(cle, titre, etapes, aide=''):
    return {'cle': cle, 'titre': titre, 'type': 'entonnoir', 'unite': 'nombre', 'aide': aide,
            'donnees': [{'libelle': l, 'valeur': v} for l, v in etapes]}


def _mois(dt):
    return f"{timezone.localtime(dt):%Y-%m}"


def _groupes_presents(compteurs):
    return [(c, l) for c, l, _ in GROUPES_STATUT if any(v.get(c) for v in compteurs.values())]


def _dep(d):
    return d.departement.libelle_service if d.departement_id else 'Non renseigné'


def _montant(d):
    """Montant retenu pour les dépenses : approuvé si la demande l'est, sinon demandé."""
    if d.statut in APPROUVEES:
        return ref(d, d.montant_approuve)
    return d.montant_demande_ref or ref(d, d.montant_demande)


def _par_mois(f):
    return defaultdict(lambda: defaultdict(Decimal))


def _toutes_dates(f):
    return {**f, 'du': date(1900, 1, 1), 'au': date(2999, 12, 31)}


# ═══════════════════════════════════════════════════════════════
# 1. VUE GLOBALE
# ═══════════════════════════════════════════════════════════════

def vue_globale(periode, f, devise):
    actives = [d for d in periode if d.statut != StatutDemande.ANNULEE]
    approuvees = [d for d in actives if d.statut in APPROUVEES]
    decidees = [d for d in actives if d.statut in APPROUVEES or d.statut == StatutDemande.REJETEE]
    taux = round(100 * len(approuvees) / len(decidees)) if decidees else 0
    en_cours = [d for d in actives if d.statut in (StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER)]
    indicateurs = [
        ind('soumises', 'Demandes soumises', len(periode)),
        ind('en_cours', 'En cours de validation', len(en_cours), lien='/demandes?vue=toutes&statut=en_validation'),
        ind('approuvees', 'Approuvées', len(approuvees)),
        ind('taux', "Taux d'approbation", taux, 'pourcentage', aide='Approuvées sur les demandes décidées (approuvées + rejetées)'),
        ind('demande', 'Montant demandé', sum((d.montant_demande_ref or ref(d, d.montant_demande) for d in actives), Decimal('0')), 'montant'),
        ind('approuve', 'Montant approuvé', sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0')), 'montant'),
    ]
    mensuel, statuts, types = defaultdict(lambda: defaultdict(int)), defaultdict(int), defaultdict(int)
    for d in periode:
        mensuel[_mois(d.soumise_le)]['nombre'] += 1
        statuts[GROUPE_DE.get(d.statut, 'en_validation')] += 1
        types[d.type_demande.libelle] += 1
    sections = [
        courbe('mensuel', 'Nombre de demandes soumises par mois', mois_periode(f), [('nombre', 'Demandes')], mensuel, 'nombre'),
        anneau('statuts', 'Demandes par statut', [(c, l, statuts[c]) for c, l, _ in GROUPES_STATUT], palette='statuts'),
        barres('types', 'Demandes par type', types, 'nombre'),
        tableau('dernieres', 'Dernières demandes soumises',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('soumise', 'Soumise le', 'date'), ('statut', 'Statut', 'texte'), ('montant', 'Montant', 'montant')],
                [_ligne_demande(d, soumise=f"{timezone.localtime(d.soumise_le):%Y-%m-%d}", montant=_montant(d) or None)
                 for d in sorted(periode, key=lambda d: d.soumise_le, reverse=True)[:50]]),
    ]
    sections[2]['orientation'] = 'verticale'   # barres verticales pour les types
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 2. MISSIONS
# ═══════════════════════════════════════════════════════════════

def missions(periode, f, devise):
    from missions.models import Pays, Ville
    liste = [d for d in periode if d.type_demande.famille == 'mission' and d.statut != StatutDemande.ANNULEE]
    tm = lambda d: (d.type_demande.parametres or {}).get('type_mission') or (d.donnees.get('mission') or {}).get('type_mission')
    m_ = lambda d: d.donnees.get('mission') or {}
    jours = sum(int(m_(d).get('nombre_jours') or 0) for d in liste)
    approuvees = [d for d in liste if d.statut in APPROUVEES]
    cout = sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0'))
    indicateurs = [
        ind('missions', 'Missions', len(liste)),
        ind('locales', 'Missions locales', sum(1 for d in liste if tm(d) == 'locale')),
        ind('hors_pays', 'Missions hors pays', sum(1 for d in liste if tm(d) == 'hors_pays')),
        ind('jours', 'Jours de mission', jours),
        ind('cout_moyen', 'Coût moyen approuvé', (cout / len(approuvees)).quantize(Decimal('1')) if approuvees else 0, 'montant'),
    ]
    mensuel, villes, pays = defaultdict(lambda: defaultdict(int)), defaultdict(int), defaultdict(int)
    for d in liste:
        mensuel[_mois(d.soumise_le)][tm(d) or 'locale'] += 1
        if m_(d).get('ville_destination'):
            villes[int(m_(d)['ville_destination'])] += 1
        if m_(d).get('pays_destination'):
            pays[int(m_(d)['pays_destination'])] += 1
    infos_villes = {v.pk: v for v in Ville.objects.filter(pk__in=villes).select_related('pays')}
    infos_pays = {p.pk: p for p in Pays.objects.filter(pk__in=pays)}
    points = sorted([{'ville': v.libelle, 'pays': v.pays.libelle, 'iso': v.pays.code_iso, 'valeur': n,
                      'lat': float(v.latitude) if v.latitude is not None else None,
                      'lon': float(v.longitude) if v.longitude is not None else None}
                     for pk, n in villes.items() if (v := infos_villes.get(pk))], key=lambda p: -p['valeur'])
    carte = {'cle': 'carte', 'titre': 'Missions par destination', 'type': 'carte', 'unite': 'nombre',
             'points': points,
             'pays': sorted([{'iso': p.code_iso, 'libelle': p.libelle, 'valeur': n} for pk, n in pays.items()
                             if (p := infos_pays.get(pk))], key=lambda p: -p['valeur'])}
    sections = [
        colonnes('mensuel', 'Missions locales et hors pays par mois', mois_periode(f),
                 [('locale', 'Locales'), ('hors_pays', 'Hors pays')], mensuel, 'nombre'),
        carte,
        anneau('types', 'Répartition par type de mission',
               [('locale', 'Missions locales', sum(1 for d in liste if tm(d) == 'locale')),
                ('hors_pays', 'Missions hors pays', sum(1 for d in liste if tm(d) == 'hors_pays'))]),
        tableau('liste', 'Missions de la période',
                [('reference', 'Référence', 'texte'), ('demandeur', 'Demandeur', 'texte'), ('destination', 'Destination', 'texte'),
                 ('depart', 'Départ', 'date'), ('jours', 'Jours', 'nombre'), ('statut', 'Statut', 'texte'),
                 ('montant', 'Montant', 'montant')],
                [_ligne_demande(d, destination=', '.join(x for x in (m_(d).get('ville_destination_libelle'),
                                                                     m_(d).get('pays_destination_libelle')) if x),
                                depart=str(m_(d).get('depart_le') or '')[:10], jours=m_(d).get('nombre_jours'),
                                montant=_montant(d)) for d in sorted(liste, key=lambda d: d.soumise_le, reverse=True)[:100]]),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 3. FINANCES ET BUDGET
# ═══════════════════════════════════════════════════════════════

def finances(periode, f, devise):
    actives = [d for d in periode if d.statut != StatutDemande.ANNULEE]
    approuvees = [d for d in actives if d.statut in APPROUVEES]
    demande = sum((d.montant_demande_ref or ref(d, d.montant_demande) for d in actives), Decimal('0'))
    approuve = sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0'))
    paye = sum((ref(d, d.montant_paye) for d in actives), Decimal('0'))
    engagements = sum((ref(d, d.solde or 0) for d in approuvees if d.statut != StatutDemande.CLOTUREE), Decimal('0'))
    indicateurs = [
        ind('demande', 'Montant demandé', demande, 'montant'),
        ind('approuve', 'Montant approuvé', approuve, 'montant'),
        ind('paye', 'Montant payé', paye, 'montant'),
        ind('engagements', 'Engagements (approuvé non payé)', engagements, 'montant'),
        ind('execution', "Taux d'exécution", round(100 * paye / approuve) if approuve else 0, 'pourcentage',
            aide='Payé sur approuvé'),
    ]
    mensuel, natures, deps = _par_mois(f), _par_mois(f), defaultdict(Decimal)
    for d in actives:
        m = _mois(d.soumise_le)
        mensuel[m]['demande'] += d.montant_demande_ref or ref(d, d.montant_demande)
        mensuel[m]['paye'] += ref(d, d.montant_paye)
        if d.statut in APPROUVEES:
            v = ref(d, d.montant_approuve)
            mensuel[m]['approuve'] += v
            natures[m][NATURE_DU_TYPE.get(d.type_demande.code, 'paiements')] += v
            deps[_dep(d)] += v
    mois = mois_periode(f)
    presentes = [(c, l) for c, l in NATURES if any(natures[m].get(c) for m in mois)] or NATURES[:1]
    sections = [
        courbe('mensuel', 'Montants demandés, approuvés et payés par mois', mois,
               [('demande', 'Demandé'), ('approuve', 'Approuvé'), ('paye', 'Payé')], mensuel),
        empilees('natures', 'Dépenses approuvées par nature et par mois', 'colonnes_empilees',
                 [(m, libelle_mois(m)) for m in mois], presentes, natures),
        barres('departements', 'Dépenses approuvées par département', deps),
        tableau('engagements', 'Engagements : demandes approuvées restant à payer',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('approuve', 'Approuvé', 'montant'), ('paye', 'Payé', 'montant'), ('reste', 'Reste à payer', 'montant')],
                sorted([_ligne_demande(d, approuve=ref(d, d.montant_approuve), paye=ref(d, d.montant_paye),
                                       reste=ref(d, d.solde or 0))
                        for d in approuvees if d.statut != StatutDemande.CLOTUREE and (d.solde or 0) > 0],
                       key=lambda l: -Decimal(l['reste']))[:100]),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 4. PAIEMENTS ET COMPTABILITÉ
# ═══════════════════════════════════════════════════════════════

def paiements(periode, f, devise, base):
    from tresorerie.models import Reglement, Reversement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    ids = [d.pk for d in periode]
    a_payer_qs = Demande.objects.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES)
    if base is not None:
        a_payer_qs = a_payer_qs.filter(pk__in=base.values('pk'))
    # En attente de paiement : quelle que soit la date de soumission (les autres filtres s'appliquent)
    a_payer = list(demandes(_toutes_dates(f), a_payer_qs))
    # Règlements : datés de la période, sur des demandes répondant aux filtres
    reglements = list(Reglement.objects.filter(annule=False, date_paiement__gte=f['du'], date_paiement__lte=f['au'],
                                               demande__in=demandes(_toutes_dates(f), base).values('pk'))
                      .select_related('demande__type_demande', 'demande__demandeur').order_by('-date_paiement'))
    paye = sum((r.montant_ref for r in reglements), Decimal('0'))
    reste = sum((ref(d, d.solde or 0) for d in a_payer), Decimal('0'))
    # Délai de paiement : de l'approbation au premier règlement (jours calendaires)
    premiers = {}
    for r in sorted(reglements, key=lambda r: r.date_paiement):
        premiers.setdefault(r.demande_id, r)
    delais = [(r.date_paiement - timezone.localtime(r.demande.approuvee_le).date()).days
              for r in premiers.values() if r.demande.approuvee_le]
    indicateurs = [
        ind('paye', 'Payé sur la période', paye, 'montant'),
        ind('reglements', 'Règlements', len(reglements)),
        ind('a_payer', 'Demandes en attente de paiement', len(a_payer), lien='/tresorerie/a-payer',
            ton='attention' if a_payer else ''),
        ind('reste', 'Montant en attente', reste, 'montant'),
        ind('delai', 'Délai moyen de paiement', round(sum(delais) / len(delais), 1) if delais else 0, 'jours',
            aide="De l'approbation au premier règlement"),
        ind('reversements', 'Reversements à percevoir', sum((r.montant_du for r in Reversement.objects.filter(
            etat='a_percevoir', demande__in=ids)), Decimal('0')), 'montant'),
    ]
    mensuel, beneficiaires = defaultdict(lambda: defaultdict(Decimal)), defaultdict(Decimal)
    for r in reglements:
        mensuel[f"{r.date_paiement:%Y-%m}"]['paye'] += r.montant_ref
    for d in a_payer:
        beneficiaires[moteur.nom(d.demandeur)] += ref(d, d.solde or 0)
    aujourd_hui = timezone.localdate()
    sections = [
        colonnes('mensuel', 'Montants payés par mois', mois_periode(f), [('paye', 'Payé')], mensuel),
        anneau('repartition', 'Paiements effectués et en attente',
               [('paye', 'Payé sur la période', paye), ('attente', 'En attente de paiement', reste)],
               unite='montant', palette='paiement'),
        barres('beneficiaires', 'Montants en attente par bénéficiaire', beneficiaires, limite=10),
        tableau('a_payer', 'Demandes en attente de paiement, les plus anciennes',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Bénéficiaire', 'texte'),
                 ('approuvee', 'Approuvée le', 'date'), ('jours', 'Attente (jours)', 'nombre'),
                 ('reste', 'Reste à payer', 'montant')],
                [_ligne_demande(d, approuvee=f"{timezone.localtime(d.approuvee_le):%Y-%m-%d}" if d.approuvee_le else None,
                                jours=(aujourd_hui - timezone.localtime(d.approuvee_le).date()).days if d.approuvee_le else None,
                                reste=ref(d, d.solde or 0))
                 for d in sorted(a_payer, key=lambda d: d.approuvee_le or timezone.now())[:50]]),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 5. DÉPARTEMENTS ET SERVICES
# ═══════════════════════════════════════════════════════════════

def departements(periode, f, devise):
    actives = [d for d in periode if d.statut != StatutDemande.ANNULEE]
    depenses, comptes = defaultdict(Decimal), defaultdict(lambda: defaultdict(int))
    recap = defaultdict(lambda: {'nombre': 0, 'demande': Decimal('0'), 'approuve': Decimal('0'), 'paye': Decimal('0')})
    for d in periode:
        comptes[_dep(d)][GROUPE_DE.get(d.statut, 'en_validation')] += 1
    for d in actives:
        r = recap[_dep(d)]
        r['nombre'] += 1
        r['demande'] += d.montant_demande_ref or ref(d, d.montant_demande)
        r['paye'] += ref(d, d.montant_paye)
        if d.statut in APPROUVEES:
            v = ref(d, d.montant_approuve)
            r['approuve'] += v
            depenses[_dep(d)] += v
    tete = max(depenses.items(), key=lambda x: x[1]) if depenses else None
    total = sum(depenses.values(), Decimal('0'))
    indicateurs = [
        ind('departements', 'Départements ayant des demandes', len(recap)),
        ind('premier', f"Plus forte dépense : {tete[0]}" if tete else 'Plus forte dépense', tete[1] if tete else 0, 'montant'),
        ind('part', 'Part du premier département', round(100 * tete[1] / total) if tete and total else 0, 'pourcentage'),
        ind('moyenne', 'Montant moyen par demande',
            (sum((r['demande'] for r in recap.values()), Decimal('0')) / len(actives)).quantize(Decimal('1')) if actives else 0,
            'montant'),
    ]
    ordre = sorted(comptes, key=lambda k: -sum(comptes[k].values()))[:12]
    sections = [
        barres('classement', 'Classement des départements par dépenses approuvées', depenses),
        empilees('statuts', 'Demandes par département et par statut', 'barres_empilees', [(k, k) for k in ordre],
                 _groupes_presents({k: comptes[k] for k in ordre}), comptes, 'nombre', palette='statuts'),
        tableau('recap', 'Synthèse par département',
                [('departement', 'Département', 'texte'), ('nombre', 'Demandes', 'nombre'), ('demande', 'Demandé', 'montant'),
                 ('approuve', 'Approuvé', 'montant'), ('paye', 'Payé', 'montant')],
                sorted([{'departement': k, **v} for k, v in recap.items()], key=lambda l: -l['approuve'])),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 6. CIRCUITS ET VALIDATIONS
# ═══════════════════════════════════════════════════════════════

def circuits(periode, f, devise):
    from workflow.models import EtapeInstance, Tache
    ctx = calendrier._contexte()
    maintenant = timezone.now()
    ids = [d.pk for d in periode]
    etapes = list(EtapeInstance.objects.filter(instance__demande__in=ids, ouverte_le__isnull=False,
                                               cloturee_le__isnull=False).select_related('etape'))
    par_etape = defaultdict(list)
    for e in etapes:
        par_etape[e.etape.libelle].append(calendrier.heures_ouvrees(e.ouverte_le, e.cloturee_le, ctx))
    taches = Tache.objects.filter(etape_instance__instance__demande__in=ids)
    en_attente = list(taches.filter(etat='en_attente').select_related(
        'etape_instance__etape', 'etape_instance__instance__demande__demandeur', 'valideur'))
    retard = [t for t in en_attente if t.echeance and t.echeance < maintenant]
    faites = taches.filter(etat='faite')
    rejets = faites.filter(decision='rejetee').count()
    approuvees = [d for d in periode if d.approuvee_le and d.soumise_le]
    delais = [(d.approuvee_le - d.soumise_le).total_seconds() / 86400 for d in approuvees]
    indicateurs = [
        ind('traitees', 'Validations traitées', faites.count()),
        ind('en_attente', 'Validations en attente', len(en_attente)),
        ind('retard', 'En retard', len(retard), ton='alerte' if retard else ''),
        ind('delai', "Délai moyen d'approbation", round(sum(delais) / len(delais), 1) if delais else 0, 'jours',
            aide='De la soumission à l\'approbation finale'),
        ind('rejets', 'Taux de rejet', round(100 * rejets / faites.count()) if faites.count() else 0, 'pourcentage'),
    ]
    mensuel = defaultdict(lambda: defaultdict(Decimal))
    nombre = defaultdict(int)
    for d in approuvees:
        m = _mois(d.approuvee_le)
        mensuel[m]['somme'] += Decimal(str((d.approuvee_le - d.soumise_le).total_seconds() / 86400))
        nombre[m] += 1
    moyennes = defaultdict(dict, {m: {'delai': (v['somme'] / nombre[m]).quantize(Decimal('0.1'))} for m, v in mensuel.items()})
    actives = [d for d in periode if d.statut != StatutDemande.ANNULEE]
    sections = [
        barres('etapes', 'Délai moyen de validation par étape (heures ouvrées)',
               {k: round(sum(v) / len(v), 1) for k, v in par_etape.items()}, 'heures'),
        courbe('evolution', "Délai moyen d'approbation par mois (jours)", mois_periode(f), [('delai', 'Délai moyen')],
               moyennes, 'jours', aide="Mois de l'approbation finale"),
        entonnoir('progression', 'Progression des demandes', [
            ('Soumises', len(actives)),
            ('Approuvées', sum(1 for d in actives if d.statut in APPROUVEES)),
            ('Payées', sum(1 for d in actives if d.statut in APPROUVEES and (d.montant_paye or 0) > 0)),
            ('Clôturées', sum(1 for d in actives if d.statut == StatutDemande.CLOTUREE)),
        ], aide='Demandes soumises sur la période, hors annulées'),
        tableau('en_attente', 'Validations en attente',
                [('reference', 'Demande', 'texte'), ('demandeur', 'Demandeur', 'texte'), ('etape', 'Étape', 'texte'),
                 ('valideur', 'Valideur', 'texte'), ('ouverte', 'Ouverte le', 'dateheure'), ('retard', 'En retard', 'oui_non')],
                [{'id': t.etape_instance.instance.demande_id, 'reference': t.etape_instance.instance.demande.reference,
                  'demandeur': moteur.nom(t.etape_instance.instance.demande.demandeur),
                  'etape': t.etape_instance.etape.libelle, 'valideur': moteur.nom(t.valideur) if t.valideur_id else '',
                  'ouverte': t.ouverte_le.isoformat() if t.ouverte_le else None, 'retard': t in retard}
                 for t in sorted(en_attente, key=lambda t: t.ouverte_le or maintenant)[:100]]),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 7. REMBOURSEMENTS ET FRAIS COMPLÉMENTAIRES
# ═══════════════════════════════════════════════════════════════

def remboursements(periode, f, devise):
    rmb = [d for d in periode if d.type_demande.code == 'RMB']
    fcm = [d for d in periode if d.type_demande.code == 'FCM']
    actifs = [d for d in rmb + fcm if d.statut != StatutDemande.ANNULEE]
    indicateurs = [
        ind('remboursements', 'Demandes de remboursement', len(rmb)),
        ind('frais', 'Frais complémentaires de mission', len(fcm)),
        ind('demande', 'Montant demandé', sum((d.montant_demande_ref or ref(d, d.montant_demande) for d in actifs), Decimal('0')), 'montant'),
        ind('approuve', 'Montant approuvé', sum((ref(d, d.montant_approuve) for d in actifs if d.statut in APPROUVEES), Decimal('0')), 'montant'),
        ind('paye', 'Montant payé', sum((ref(d, d.montant_paye) for d in actifs), Decimal('0')), 'montant'),
    ]
    # Frais complémentaires par mission : approuvés / en validation / rejetés
    par_mission = defaultdict(lambda: defaultdict(Decimal))
    for d in fcm:
        mission = d.demande_parent.reference if d.demande_parent_id else 'Sans mission'
        groupe = GROUPE_DE.get(d.statut, 'en_validation')
        if groupe == 'annulee':
            continue
        par_mission[mission][groupe] += d.montant_demande_ref or ref(d, d.montant_demande)
    missions_ordre = sorted(par_mission, key=lambda k: -sum(par_mission[k].values()))[:10]
    statuts = defaultdict(int)
    mensuel = defaultdict(lambda: defaultdict(Decimal))
    for d in rmb:
        statuts[GROUPE_DE.get(d.statut, 'en_validation')] += 1
        if d.statut != StatutDemande.ANNULEE:
            m = _mois(d.soumise_le)
            mensuel[m]['demande'] += d.montant_demande_ref or ref(d, d.montant_demande)
            if d.statut in APPROUVEES:
                mensuel[m]['approuve'] += ref(d, d.montant_approuve)
    sections = [
        empilees('par_mission', 'Frais complémentaires par mission', 'barres_empilees',
                 [(k, k) for k in missions_ordre], _groupes_presents({k: par_mission[k] for k in missions_ordre}),
                 par_mission, 'montant', palette='statuts'),
        anneau('statuts', 'Remboursements par statut', [(c, l, statuts[c]) for c, l, _ in GROUPES_STATUT], palette='statuts'),
        courbe('mensuel', 'Évolution mensuelle des remboursements', mois_periode(f),
               [('demande', 'Demandé'), ('approuve', 'Approuvé')], mensuel),
        tableau('liste', 'Remboursements et frais complémentaires de la période',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('mission', 'Mission', 'texte'), ('statut', 'Statut', 'texte'), ('montant', 'Montant', 'montant')],
                [_ligne_demande(d, mission=d.demande_parent.reference if d.demande_parent_id else '', montant=_montant(d))
                 for d in sorted(rmb + fcm, key=lambda d: d.soumise_le, reverse=True)[:100]]),
    ]
    return indicateurs, sections


# ═══════════════════════════════════════════════════════════════
# 8. RÉCEPTIONS CLIENTS
# ═══════════════════════════════════════════════════════════════

def receptions(periode, f, devise):
    frc = [d for d in periode if d.type_demande.code == 'FRC' and d.statut != StatutDemande.ANNULEE]
    approuvees = [d for d in frc if d.statut in APPROUVEES]
    montant = sum((_montant(d) for d in frc), Decimal('0'))
    participants = sum(int(d.donnees.get('nombre_participants') or 0) for d in frc)
    indicateurs = [
        ind('receptions', 'Réceptions', len(frc)),
        ind('montant', 'Dépenses (approuvé ou demandé)', montant, 'montant'),
        ind('approuve', 'Montant approuvé', sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0')), 'montant'),
        ind('moyenne', 'Coût moyen par réception', (montant / len(frc)).quantize(Decimal('1')) if frc else 0, 'montant'),
        ind('participants', 'Coût moyen par participant',
            (montant / participants).quantize(Decimal('1')) if participants else 0, 'montant'),
    ]
    mensuel, deps, nb = defaultdict(lambda: defaultdict(Decimal)), defaultdict(Decimal), defaultdict(int)
    for d in frc:
        mensuel[_mois(d.soumise_le)]['montant'] += _montant(d)
        deps[_dep(d)] += _montant(d)
        nb[_dep(d)] += 1
    sections = [
        colonnes('mensuel', 'Dépenses de réception par mois', mois_periode(f), [('montant', 'Dépenses')], mensuel),
        barres('departements', 'Dépenses de réception par département', deps),
        anneau('repartition', 'Nombre de réceptions par département', [(k, k, v) for k, v in nb.items()],
               teintes=_teintes_departements()),
        tableau('liste', 'Réceptions de la période',
                [('reference', 'Référence', 'texte'), ('demandeur', 'Demandeur', 'texte'), ('client', 'Client', 'texte'),
                 ('date', 'Date', 'date'), ('participants', 'Participants', 'nombre'), ('statut', 'Statut', 'texte'),
                 ('montant', 'Montant', 'montant')],
                [_ligne_demande(d, client=d.donnees.get('client', ''), date=str(d.donnees.get('date_reception') or '')[:10],
                                participants=d.donnees.get('nombre_participants'), montant=_montant(d))
                 for d in sorted(frc, key=lambda d: d.soumise_le, reverse=True)[:100]]),
    ]
    return indicateurs, sections


CALCULS = {'global': vue_globale, 'missions': missions, 'finances': finances, 'departements': departements,
           'circuits': circuits, 'remboursements': remboursements, 'receptions': receptions}


def themes(user):
    if not acces_statistiques(user):
        return []
    return [{'code': c, 'libelle': l, 'icone': i, 'court': k} for c, l, i, k in THEMES]


def statistiques(user, theme, params):
    if not acces_statistiques(user):
        raise Interdit("Les statistiques ne vous sont pas accessibles.")
    libelles = {c: l for c, l, _, _ in THEMES}
    if theme not in libelles:
        raise Interdit("Tableau de statistiques inconnu.")
    f = filtres(params)
    q = filtre_perimetre(user)
    base = Demande.objects.filter(q) if q is not None else None
    periode = list(demandes(f, base))
    devise = ParametreSysteme.charger().devise_reference
    if theme == 'paiements':
        indicateurs, sections = paiements(periode, f, devise, base)
    else:
        indicateurs, sections = CALCULS[theme](periode, f, devise)
    return {'theme': theme, 'titre': libelles[theme], 'devise': devise, 'du': f['du'].isoformat(),
            'au': f['au'].isoformat(), 'genere_le': timezone.now().isoformat(),
            'indicateurs': indicateurs, 'sections': sections}
