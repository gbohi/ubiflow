"""
Accueil de synthèse : comprendre en quelques secondes ce qui se passe et ce qu'il
faut faire. Bloc « À faire » commun (tout ce qui attend une action de
l'utilisateur, les plus anciens d'abord), indicateurs, listes et graphiques
selon la vue (collaborateur, valideur, direction, finances), notifications
récentes, activité récente groupée par demande, actions rapides et accès.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from api.models import AffectationResponsabilite, ParametreSysteme
from api.permissions import filtre_perimetre, get_roles, is_admin, is_admin_finances, is_comptable
from demandes.models import Demande, StatutDemande
from workflow import moteur
from workflow.models import Action, Tache

from .indicateurs import APPROUVEES, MOIS, ref

PROFILS = [('direction', 'Direction générale'), ('finances', 'Finances'), ('valideur', 'Validations'),
           ('collaborateur', 'Mes demandes')]
FAMILLES = [('MLO', 'Missions locales'), ('MHP', 'Missions hors pays'), ('FRC', 'Réceptions client'), ('PAI', 'Paiements'),
            ('RMB', 'Remboursements')]


def _titulaire(user, *codes):
    d = timezone.localdate()
    return AffectationResponsabilite.objects.filter(user=user, responsabilite__code__in=codes, date_debut__lte=d).filter(
        Q(date_fin__isnull=True) | Q(date_fin__gte=d)).exists()


def profils(user):
    roles = get_roles(user)
    p = []
    if is_admin(user) or 'direction' in roles or _titulaire(user, 'DG'):
        p.append('direction')
    if is_comptable(user) or is_admin_finances(user) or _titulaire(user, 'DAF', 'CHEF_COMPTABLE'):
        p.append('finances')
    if (Tache.objects.filter(Q(valideur=user) | Q(traitee_par=user)).exists()
            or AffectationResponsabilite.objects.filter(user=user, date_fin__isnull=True).exists()):
        p.append('valideur')
    p.append('collaborateur')
    return p


def _kpi(cle, libelle, valeur, sous_titre='', format='nombre', lien=None, ton='', icone='ri-file-list-3-line'):
    return {'cle': cle, 'libelle': libelle, 'valeur': str(valeur) if isinstance(valeur, Decimal) else valeur,
            'sous_titre': sous_titre, 'format': format, 'lien': lien, 'ton': ton, 'icone': icone}


def _ligne(d, **autres):
    return {'id': d.pk, 'reference': d.reference or 'Brouillon', 'type': d.type_demande.libelle, 'type_code': d.type_demande.code,
            'type_icone': d.type_demande.icone, 'objet': d.objet, 'statut': d.statut, 'statut_libelle': d.get_statut_display(),
            'demandeur': moteur.nom(d.demandeur), **autres}


def _liste(cle, titre, lignes, lien_tout=None, vide='Rien à signaler.', colonnes=None):
    return {'cle': cle, 'titre': titre, 'lignes': lignes, 'lien_tout': lien_tout, 'vide': vide, 'colonnes': colonnes or []}


def _mission(d):
    return (d.donnees or {}).get('mission') or {}


def _montant(v):
    return f"{Decimal(v or 0):,.0f}".replace(',', '\u00a0')


def _montant_ligne(d):
    v = d.montant_approuve if d.montant_approuve is not None else d.montant_demande
    return str(ref(d, v)) if v is not None else None


def _pluriel(n, singulier, pluriel=None, zero=True):
    """« 1 demande », « 3 demandes » ; chaîne vide pour 0 si zero=False."""
    if not n and not zero:
        return ''
    return f"{n} {singulier if n <= 1 else (pluriel or singulier + 's')}"


def _duree(depuis):
    """Ancienneté lisible : « 3 h », « 2 j », « 3 sem. »."""
    if not depuis:
        return ''
    secondes = (timezone.now() - depuis).total_seconds()
    if secondes < 3600:
        return f"{max(1, int(secondes // 60))} min"
    if secondes < 86400:
        return f"{int(secondes // 3600)} h"
    jours = int(secondes // 86400)
    return f"{jours} j" if jours < 21 else f"{jours // 7} sem."


def _etape(d):
    if d.statut == StatutDemande.EN_VALIDATION:
        t = (Tache.objects.filter(etape_instance__instance__demande=d, etat='en_attente')
             .select_related('etape_instance__etape').first())
        lib = t.etape_instance.etape.libelle if t else ""
        return f"étape : {lib[:1].lower()}{lib[1:]}" if t else ''
    return {StatutDemande.BROUILLON: 'non soumis', StatutDemande.A_CORRIGER: 'à corriger',
            StatutDemande.APPROUVEE: 'approuvée', StatutDemande.EN_ATTENTE_CLOTURE: 'clôture attendue'}.get(d.statut, '')


# ═══════════════════════════════════════════════════════════════
# À FAIRE : tout ce qui attend une action de l'utilisateur
# ═══════════════════════════════════════════════════════════════

def a_faire(user, limite=8):
    """Éléments {motif, action, lien…} triés du plus ancien au plus récent, et leur nombre total."""
    from missions.cloture import peut_controler
    from missions.models import ClotureMission
    from tresorerie.models import Reversement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    elements = []

    def ajouter(d, motif, action, depuis, lien=None, info='', retard=False):
        elements.append(_ligne(d, motif=motif, action=action, lien=lien or f"/demandes/{d.pk}", info=info, retard=retard,
                               montant=_montant_ligne(d), depuis=depuis.isoformat() if depuis else None, _tri=depuis or timezone.now()))

    maintenant = timezone.now()
    for t in (Tache.objects.filter(etat='en_attente').filter(moteur.filtre_taches_de(user))
              .select_related('valideur', 'etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                              'etape_instance__instance__demande__demandeur')):
        en_retard = bool(t.echeance and t.echeance < maintenant)
        info = t.etape_instance.etape.libelle + (f" · pour {moteur.nom(t.valideur)}" if t.valideur_id != user.pk else '')
        ajouter(t.etape_instance.instance.demande, 'a_valider', 'Valider', t.ouverte_le, info=info, retard=en_retard)
    if is_comptable(user) or is_admin_finances(user):
        for d in (Demande.objects.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES)
                  .select_related('type_demande', 'demandeur')):
            ajouter(d, 'a_payer', 'Payer', d.approuvee_le,
                    info=f"approuvée le {timezone.localtime(d.approuvee_le):%d/%m}" if d.approuvee_le else '')
    for c in ClotureMission.objects.filter(etat='soumise').select_related('demande__type_demande', 'demande__demandeur'):
        if peut_controler(c.demande, user):
            ajouter(c.demande, 'cloture_a_controler', 'Contrôler', c.soumise_le, info='clôture à contrôler')
    mes = Demande.objects.filter(demandeur=user).select_related('type_demande', 'demandeur')
    for d in mes.filter(statut=StatutDemande.A_CORRIGER):
        ajouter(d, 'a_corriger', 'Corriger', d.updated_at, info='retournée pour correction')
    for d in mes.filter(statut=StatutDemande.EN_ATTENTE_CLOTURE):
        if not ClotureMission.objects.filter(demande=d, etat__in=('soumise', 'validee')).exists():
            retour = str(_mission(d).get('retour_le', ''))
            ajouter(d, 'a_cloturer', 'Déclarer mes dépenses', d.approuvee_le,
                    info=f"retour le {retour[8:10]}/{retour[5:7]} · rapport attendu" if retour else 'rapport attendu')
    for r in Reversement.objects.filter(demande__demandeur=user, etat='a_percevoir').select_related('demande__type_demande', 'demande__demandeur'):
        ajouter(r.demande, 'reversement', 'Voir', r.cree_le,
                info=f"reversement de {_montant(r.montant_du)} {r.devise} à effectuer")
    elements.sort(key=lambda e: (not e['retard'], e['_tri']))
    for e in elements:
        e.pop('_tri')
    return elements[:limite], len(elements)


def _resume(nombre):
    if not nombre:
        return 'Rien ne vous attend pour le moment'
    return f"{nombre} demande{'s attendent' if nombre > 1 else ' attend'} une action de votre part"


# ═══════════════════════════════════════════════════════════════
# PROFILS
# ═══════════════════════════════════════════════════════════════

def collaborateur(user):
    from missions.models import ClotureMission
    mes = Demande.objects.filter(demandeur=user).select_related('type_demande', 'demandeur')
    soumises = mes.filter(reference__isnull=False)
    a_corriger = list(mes.filter(statut=StatutDemande.A_CORRIGER))
    a_cloturer = [d for d in mes.filter(statut=StatutDemande.EN_ATTENTE_CLOTURE)
                  if not ClotureMission.objects.filter(demande=d, etat__in=('soumise', 'validee')).exists()]
    aujourd_hui = timezone.localdate().isoformat()
    prochaines = sorted([d for d in mes.filter(type_demande__famille='mission',
                                                   statut__in=(StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE))
                         if str(_mission(d).get('depart_le', ''))[:10] >= aujourd_hui], key=lambda d: _mission(d).get('depart_le'))
    annee = timezone.localdate().year
    en_validation = list(mes.filter(statut=StatutDemande.EN_VALIDATION))
    approuvees = [d for d in soumises.filter(statut__in=APPROUVEES)]
    montant_approuve = sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0'))
    devise = ParametreSysteme.charger().devise_reference
    plus_ancienne = min((d.soumise_le for d in en_validation if d.soumise_le), default=None)
    actions = len(a_corriger) + len(a_cloturer)
    kpis = [
        _kpi('toutes', 'Mes demandes', soumises.count(), f"{soumises.filter(soumise_le__year=annee).count()} cette année",
             lien='/demandes', icone='ri-file-list-3-line'),
        _kpi('en_cours', 'En validation', len(en_validation),
             f"la plus ancienne depuis {_duree(plus_ancienne)}" if plus_ancienne else 'Aucune en attente',
             lien='/demandes?statut=en_validation', icone='ri-loader-2-line'),
        _kpi('approuvees', 'Approuvées', len(approuvees), f"{_montant(montant_approuve)} {devise}" if approuvees else 'Aucune pour le moment',
             lien='/demandes?statut=approuvee', icone='ri-checkbox-circle-line'),
        _kpi('actions', 'Actions attendues', actions,
             ' · '.join(x for x in [_pluriel(len(a_corriger), 'à corriger', 'à corriger', zero=False), _pluriel(len(a_cloturer), 'mission à clôturer', 'missions à clôturer', zero=False)] if x)
             or 'Rien à faire', lien='/demandes?statut=a_corriger' if a_corriger else '/demandes?statut=en_attente_cloture',
             ton='attention' if actions else '', icone='ri-error-warning-line'),
    ]
    en_cours = mes.exclude(statut__in=(StatutDemande.CLOTUREE, StatutDemande.ANNULEE, StatutDemande.REJETEE)).order_by('-updated_at')
    listes = [
        _liste('en_cours', 'Mes demandes en cours', [_ligne(d, montant=_montant_ligne(d), info=_etape(d)) for d in en_cours[:5]],
               '/demandes', 'Aucune demande en cours.'),
        _liste('prochaines', 'Mes prochaines missions', [_ligne(d, info=f"{_mission(d).get('ville_destination_libelle', '')} · départ le "
                                                                       f"{str(_mission(d).get('depart_le', ''))[8:10]}/{str(_mission(d).get('depart_le', ''))[5:7]}")
                                                          for d in prochaines[:5]], None, 'Aucune mission à venir.'),
    ]
    return kpis, listes, []


def valideur(user):
    maintenant = timezone.now()
    en_attente = list(Tache.objects.filter(etat='en_attente').filter(moteur.filtre_taches_de(user))
                      .select_related('etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                                      'etape_instance__instance__demande__demandeur').order_by('ouverte_le'))
    retard = [t for t in en_attente if t.echeance and t.echeance < maintenant]
    faites = Tache.objects.filter(traitee_par=user, etat='faite')
    plus_ancienne = en_attente[0].ouverte_le if en_attente else None
    kpis = [
        _kpi('a_valider', 'À valider', len(en_attente),
             f"la plus ancienne depuis {_duree(plus_ancienne)}" if plus_ancienne else 'Rien en attente', lien='/validations',
             ton='attention' if en_attente else '', icone='ri-checkbox-multiple-line'),
        _kpi('retard', 'En retard', len(retard), 'échéance dépassée' if retard else 'Aucun retard', lien='/validations',
             ton='alerte' if retard else '',
             icone='ri-alarm-warning-line'),
        _kpi('aujourdhui', "Validées aujourd'hui", faites.filter(decision='approuvee', traitee_le__date=timezone.localdate()).count(),
             'approbations du jour', icone='ri-check-double-line'),
        _kpi('retournees', 'Retournées ou rejetées', faites.filter(decision__in=('retournee', 'rejetee'),
                                                                   traitee_le__gte=maintenant - timedelta(days=30)).count(),
             'sur les 30 derniers jours', icone='ri-arrow-go-back-line'),
    ]
    recentes = (Tache.objects.filter(traitee_par=user, etat='faite').select_related(
        'etape_instance__etape', 'etape_instance__instance__demande__type_demande', 'etape_instance__instance__demande__demandeur')
        .order_by('-traitee_le')[:5])
    decisions = {'approuvee': 'Approuvée', 'retournee': 'Retournée', 'rejetee': 'Rejetée'}
    listes = [_liste('traitees', 'Mes dernières décisions', [
        _ligne(t.etape_instance.instance.demande, montant=_montant_ligne(t.etape_instance.instance.demande),
               info=f"{decisions.get(t.decision, t.decision)} le {timezone.localtime(t.traitee_le):%d/%m} · {t.etape_instance.etape.libelle}")
        for t in recentes], '/validations', 'Aucune décision récente.')]
    return kpis, listes, []


def direction(user):
    from tresorerie.models import Reversement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    q = filtre_perimetre(user)
    base = Demande.objects.filter(q) if q is not None else Demande.objects.all()
    annee = timezone.localdate().year
    de_l_annee = list(base.filter(reference__isnull=False, soumise_le__year=annee).select_related('type_demande', 'demandeur'))
    maintenant = timezone.now().isoformat()
    en_cours = [d for d in base.filter(type_demande__famille='mission', statut__in=APPROUVEES).select_related('type_demande')
                if str(_mission(d).get('depart_le', '')) <= maintenant <= str(_mission(d).get('retour_le', '')) + 'Z']
    approuve = sum((ref(d, d.montant_approuve) for d in de_l_annee if d.statut in APPROUVEES), Decimal('0'))
    kpis = [
        _kpi('total', 'Demandes', len(de_l_annee), f"soumises en {annee}", lien='/demandes?vue=toutes',
             icone='ri-stack-line'),
        _kpi('attente', 'En attente de validation', base.filter(statut=StatutDemande.EN_VALIDATION).count(),
             _pluriel(Tache.objects.filter(etat='en_attente', echeance__lt=timezone.now()).count(), 'en retard', 'en retard', zero=False) or 'aucune en retard',
             lien='/demandes?vue=toutes&statut=en_validation', icone='ri-time-line'),
        _kpi('missions', 'Missions en cours', len(en_cours), "collaborateurs en déplacement aujourd'hui", icone='ri-road-map-line'),
        _kpi('budget', f'Approuvé en {annee}', approuve, _pluriel(len([d for d in de_l_annee if d.statut in APPROUVEES]), 'demande approuvée', 'demandes approuvées'),
             'montant', '/tableaux-de-bord?profil=direction',
             icone='ri-money-dollar-circle-line'),
    ]
    par_famille = defaultdict(int)
    codes = dict(FAMILLES)
    for d in de_l_annee:
        par_famille[codes.get(d.type_demande.code, 'Autres demandes')] += 1
    # dépenses approuvées des 6 derniers mois (par mois d'approbation)
    mois = []
    a, m = timezone.localdate().year, timezone.localdate().month
    for _ in range(6):
        mois.insert(0, (a, m))
        a, m = (a - 1, 12) if m == 1 else (a, m - 1)
    debut = date(mois[0][0], mois[0][1], 1)
    valeurs = defaultdict(Decimal)
    for d in base.filter(statut__in=APPROUVEES, approuvee_le__date__gte=debut).select_related('type_demande'):
        valeurs[(d.approuvee_le.year, d.approuvee_le.month)] += ref(d, d.montant_approuve)
    graphes = [
        {'cle': 'categories', 'titre': 'Répartition des demandes par catégorie', 'type': 'barres', 'unite': 'nombre',
         'donnees': [{'libelle': l, 'valeur': v} for l, v in sorted(par_famille.items(), key=lambda x: -x[1])]},
        {'cle': 'depenses', 'titre': 'Dépenses approuvées, 6 derniers mois', 'type': 'colonnes', 'unite': 'montant',
         'series': [{'cle': 'approuve', 'libelle': 'Approuvé'}],
         'donnees': [{'libelle': f"{MOIS[mm - 1]} {str(aa)[2:]}", 'valeurs': {'approuve': str(valeurs[(aa, mm)])}} for aa, mm in mois]},
    ]
    attention = []
    for t in Tache.objects.filter(etat='en_attente', echeance__lt=timezone.now()).select_related(
            'valideur', 'etape_instance__instance__demande__type_demande', 'etape_instance__instance__demande__demandeur')[:5]:
        attention.append(_ligne(t.etape_instance.instance.demande, info=f"Validation en retard chez {moteur.nom(t.valideur)}", ton='alerte'))
    seuil = timezone.now() - timedelta(days=30)
    for d in base.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES,
                         approuvee_le__lt=seuil).select_related('type_demande', 'demandeur')[:5]:
        attention.append(_ligne(d, info='Approuvée depuis plus de 30 jours, non payée', ton='attention'))
    for d in base.filter(statut=StatutDemande.EN_VALIDATION).exclude(alertes=[]).select_related('type_demande', 'demandeur')[:5]:
        attention.append(_ligne(d, info=d.alertes[0].get('message', ''), ton='attention'))
    for r in Reversement.objects.filter(etat='a_percevoir', demande__in=base).select_related('demande__type_demande', 'demande__demandeur')[:5]:
        attention.append(_ligne(r.demande, info=f"Reversement de {r.montant_du:,.0f} {r.devise} à percevoir".replace(',', ' '), ton='attention'))
    listes = [_liste('attention', 'Demandes nécessitant une attention particulière', attention[:10], None,
                     'Aucune demande ne nécessite d\'attention particulière.')]
    return kpis, listes, graphes


def finances(user):
    from tresorerie.models import Reglement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    annee = timezone.localdate().year
    a_payer = list(Demande.objects.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES)
                   .select_related('type_demande', 'demandeur').order_by('-approuvee_le'))
    approuvees = list(Demande.objects.filter(statut__in=APPROUVEES, approuvee_le__year=annee).select_related('type_demande', 'departement'))
    reglements = Reglement.objects.filter(annule=False).select_related('demande__type_demande', 'demande__demandeur').order_by('-date_paiement', '-id')
    from tresorerie.models import Reversement
    total_approuve = sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0'))
    de_l_annee = reglements.filter(date_paiement__year=annee)
    paye = de_l_annee.aggregate(s=Sum('montant_ref'))['s'] or Decimal('0')
    ce_mois = de_l_annee.filter(date_paiement__month=timezone.localdate().month).count()
    a_percevoir = Reversement.objects.filter(etat='a_percevoir')
    plus_ancienne = min((d.approuvee_le for d in a_payer if d.approuvee_le), default=None)
    kpis = [
        _kpi('attente', 'À payer', sum((ref(d, d.solde or 0) for d in a_payer), Decimal('0')),
             f"{_pluriel(len(a_payer), 'demande')}, la plus ancienne approuvée il y a {_duree(plus_ancienne)}" if plus_ancienne else 'Rien à payer',
             'montant', '/tresorerie/a-payer', 'attention' if a_payer else '', 'ri-wallet-3-line'),
        _kpi('paye', f'Payé en {annee}', paye, f"{_pluriel(de_l_annee.count(), 'paiement')}, dont {ce_mois} ce mois-ci",
             'montant', icone='ri-hand-coin-line'),
        _kpi('approuve', f'Approuvé en {annee}', total_approuve,
             f"{round(paye * 100 / total_approuve)} % déjà payé" if total_approuve else 'Aucune approbation', 'montant',
             icone='ri-checkbox-circle-line'),
        _kpi('reversements', 'Reversements à percevoir', a_percevoir.aggregate(s=Sum('montant_du'))['s'] or Decimal('0'),
             _pluriel(a_percevoir.count(), 'reversement en attente', 'reversements en attente', zero=False) or 'Aucun reversement en attente',
             'montant', '/tresorerie/reversements', icone='ri-arrow-go-back-line'),
    ]
    par_dep = defaultdict(Decimal)
    for d in approuvees:
        par_dep[d.departement.libelle_service if d.departement_id else 'Non renseigné'] += ref(d, d.montant_approuve)
    graphes = [{'cle': 'departements', 'titre': f'Dépenses par département ({annee})', 'type': 'barres', 'unite': 'montant',
                'donnees': [{'libelle': l, 'valeur': str(v)} for l, v in sorted(par_dep.items(), key=lambda x: -x[1])[:8]]}]
    avec_fcm = (Demande.objects.filter(type_demande__famille='mission', demandes_rattachees__type_demande__code='FCM')
                .exclude(demandes_rattachees__statut__in=('brouillon', 'rejetee', 'annulee')).distinct()
                .select_related('type_demande', 'demandeur').order_by('-updated_at')[:5])
    listes = [
        _liste('paiements', 'Paiements récents', [_ligne(r.demande, montant=str(r.montant_ref),
                                                         info=f"{r.get_mode_display()} le {r.date_paiement:%d/%m/%Y}") for r in reglements[:6]],
               None, 'Aucun paiement enregistré.'),
        _liste('fcm', 'Missions avec frais complémentaires', [_ligne(d) for d in avec_fcm], None, 'Aucune mission avec frais complémentaires.'),
    ]
    return kpis, listes, graphes


CALCULS = {'collaborateur': collaborateur, 'valideur': valideur, 'direction': direction, 'finances': finances}


def accueil(user, profil=None):
    disponibles = profils(user)
    profil = profil if profil in disponibles else disponibles[0]
    kpis, listes, graphes = CALCULS[profil](user)
    elements, total = a_faire(user)
    from notifications.models import Notification
    notifs = Notification.objects.filter(destinataire=user).order_by('-creee_le')[:5]
    actions = [{'libelle': 'Mission', 'icone': 'ri-road-map-line', 'lien': '/demandes/nouvelle', 'code': 'MLO'},
               {'libelle': 'Mission hors pays', 'icone': 'ri-flight-takeoff-line', 'lien': '/demandes/nouvelle', 'code': 'MHP'},
               {'libelle': 'Remboursement', 'icone': 'ri-refund-2-line', 'lien': '/demandes/nouvelle', 'code': 'RMB'},
               {'libelle': 'Autre demande', 'icone': 'ri-add-circle-line', 'lien': '/demandes/nouvelle', 'code': None}]
    # Accès propres au rôle (le menu donne déjà les autres)
    acces = []
    if is_comptable(user) or is_admin_finances(user):
        acces += [{'libelle': 'À payer', 'icone': 'ri-wallet-3-line', 'lien': '/tresorerie/a-payer'},
                  {'libelle': 'Reversements', 'icone': 'ri-arrow-go-back-line', 'lien': '/tresorerie/reversements'}]
    if 'valideur' in disponibles and not acces:
        acces.append({'libelle': 'À valider', 'icone': 'ri-checkbox-multiple-line', 'lien': '/validations'})
    acces.append({'libelle': 'Tableaux de bord', 'icone': 'ri-dashboard-3-line', 'lien': '/tableaux-de-bord'})
    acces = acces[:3]  # la barre tient sur une ligne ; le menu donne le reste
    libelles = dict(PROFILS)
    return {
        'prenom': user.prenom or user.username, 'aujourdhui': timezone.localdate().isoformat(),
        'devise': ParametreSysteme.charger().devise_reference,
        'profils': [{'code': c, 'libelle': libelles[c]} for c in disponibles], 'profil': profil,
        'resume': _resume(total), 'a_faire': elements, 'a_faire_total': total,
        'kpis': kpis, 'listes': listes, 'graphes': graphes,
        'actions_rapides': actions, 'acces': acces,
        'notifications': [{'id': n.pk, 'titre': n.titre, 'message': n.message, 'lien': n.lien, 'lue': n.lue,
                           'creee_le': n.creee_le.isoformat()} for n in notifs],
        'activites': activites_groupees(user),
    }


def activites_groupees(user, limite=4):
    """Dernières actions sur mes demandes ou faites par moi, regroupées par demande."""
    actions = (Action.objects.filter(Q(demande__demandeur=user) | Q(auteur_reel=user)).exclude(type='creation')
               .select_related('demande__type_demande', 'auteur_reel').order_by('-horodatage')[:60])
    groupes = {}
    for a in actions:
        g = groupes.get(a.demande_id)
        if g is None:
            if len(groupes) >= limite:
                continue
            g = groupes[a.demande_id] = {
                'demande': a.demande_id, 'reference': a.demande.reference or 'Brouillon', 'objet': a.demande.objet,
                'type_code': a.demande.type_demande.code,
                'derniere': {'type': a.get_type_display(), 'auteur': moteur.nom(a.auteur_reel) if a.auteur_reel_id else 'Système',
                             'le': a.horodatage.isoformat()},
                'compte': {}}
        g['compte'][a.get_type_display()] = g['compte'].get(a.get_type_display(), 0) + 1
    return [{**g, 'compte': [{'type': t, 'nombre': n} for t, n in g['compte'].items()]} for g in groupes.values()]
