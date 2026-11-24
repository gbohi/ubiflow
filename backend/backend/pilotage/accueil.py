"""
Accueil de synthèse : comprendre en quelques secondes ce qui se passe et ce qu'il
faut faire. Contenu selon le profil (collaborateur, valideur, direction,
finances) ; blocs communs : actions rapides, alertes, notifications récentes,
dernières activités, raccourcis.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from api import organisation as org
from api.models import AffectationResponsabilite, ParametreSysteme
from api.permissions import filtre_perimetre, get_roles, is_admin, is_admin_finances, is_comptable
from demandes.models import Demande, StatutDemande
from workflow import moteur
from workflow.models import Action, Tache

from .indicateurs import APPROUVEES, MOIS, ref

PROFILS = [('direction', 'Direction générale'), ('finances', 'Finances et comptabilité'), ('valideur', 'Validations'),
           ('collaborateur', 'Mon activité')]
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
    prochaines = sorted([d for d in mes.filter(type_demande__famille='mission', statut__in=APPROUVEES)
                         if str(_mission(d).get('depart_le', ''))[:10] >= aujourd_hui], key=lambda d: _mission(d).get('depart_le'))
    kpis = [
        _kpi('toutes', 'Toutes mes demandes', soumises.count(), 'Depuis le début', lien='/demandes', icone='ri-file-list-3-line'),
        _kpi('en_cours', 'En cours de validation', mes.filter(statut=StatutDemande.EN_VALIDATION).count(), 'À suivre',
             lien='/demandes?statut=en_validation', icone='ri-loader-2-line'),
        _kpi('approuvees', 'Approuvées', soumises.filter(statut__in=APPROUVEES).count(), 'Depuis le début',
             lien='/demandes?statut=approuvee', icone='ri-checkbox-circle-line'),
        _kpi('actions', 'Actions attendues', len(a_corriger) + len(a_cloturer), 'Corrections et clôtures',
             lien='/demandes?statut=a_corriger', ton='attention' if (a_corriger or a_cloturer) else '', icone='ri-error-warning-line'),
    ]
    listes = [
        _liste('dernieres', 'Mes dernières demandes', [_ligne(d) for d in mes.order_by('-updated_at')[:5]], '/demandes',
               'Aucune demande pour le moment.'),
        _liste('prochaines', 'Mes prochaines missions', [_ligne(d, info=f"{_mission(d).get('ville_destination_libelle', '')} · départ le "
                                                                       f"{str(_mission(d).get('depart_le', ''))[8:10]}/{str(_mission(d).get('depart_le', ''))[5:7]}")
                                                          for d in prochaines[:5]], None, 'Aucune mission à venir.'),
        _liste('a_corriger', 'Retournées pour correction', [_ligne(d) for d in a_corriger[:5]], '/demandes?statut=a_corriger',
               'Aucune demande à corriger.'),
        _liste('rapports', 'Rapports de mission à soumettre', [_ligne(d, info='Clôture à déclarer') for d in a_cloturer[:5]],
               '/demandes?statut=en_attente_cloture', 'Aucune clôture en attente.'),
    ]
    alertes = []
    if a_corriger:
        alertes.append({'ton': 'attention', 'texte': f"{len(a_corriger)} demande(s) retournée(s) pour correction.",
                        'lien': '/demandes?statut=a_corriger'})
    if a_cloturer:
        alertes.append({'ton': 'attention', 'texte': f"{len(a_cloturer)} mission(s) à clôturer : déclarez vos dépenses et joignez le rapport.",
                        'lien': '/demandes?statut=en_attente_cloture'})
    from tresorerie.models import Reversement
    dus = Reversement.objects.filter(demande__demandeur=user, etat='a_percevoir')
    if dus.exists():
        alertes.append({'ton': 'alerte', 'texte': f"Reversement à effectuer : {dus.aggregate(s=Sum('montant_du'))['s']:,.0f} "
                                                  f"{ParametreSysteme.charger().devise_reference}".replace(',', ' '),
                        'lien': f"/demandes/{dus.first().demande_id}"})
    return kpis, listes, [], alertes


def valideur(user):
    maintenant = timezone.now()
    en_attente = list(Tache.objects.filter(etat='en_attente').filter(moteur.filtre_taches_de(user))
                      .select_related('etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                                      'etape_instance__instance__demande__demandeur').order_by('ouverte_le'))
    retard = [t for t in en_attente if t.echeance and t.echeance < maintenant]
    faites = Tache.objects.filter(traitee_par=user, etat='faite')
    kpis = [
        _kpi('a_valider', 'Demandes à valider', len(en_attente), 'En attente de votre décision', lien='/validations',
             ton='attention' if en_attente else '', icone='ri-checkbox-multiple-line'),
        _kpi('retard', 'En retard', len(retard), 'Échéance dépassée', lien='/validations', ton='alerte' if retard else '',
             icone='ri-alarm-warning-line'),
        _kpi('aujourdhui', "Validées aujourd'hui", faites.filter(decision='approuvee', traitee_le__date=timezone.localdate()).count(),
             'Approbations du jour', icone='ri-check-double-line'),
        _kpi('retournees', 'Retournées ou rejetées', faites.filter(decision__in=('retournee', 'rejetee'),
                                                                   traitee_le__gte=maintenant - timedelta(days=30)).count(),
             '30 derniers jours', icone='ri-arrow-go-back-line'),
    ]
    lignes = [_ligne(t.etape_instance.instance.demande, etape=t.etape_instance.etape.libelle,
                     depuis=t.ouverte_le.isoformat() if t.ouverte_le else None, retard=t in retard,
                     pour_compte_de=moteur.nom(t.valideur) if t.valideur_id != user.pk else None) for t in en_attente[:10]]
    listes = [_liste('validations', 'Mes validations en attente', lignes, '/validations', 'Aucune validation en attente.')]
    alertes = [{'ton': 'alerte', 'texte': f"{len(retard)} validation(s) en retard.", 'lien': '/validations'}] if retard else []
    return kpis, listes, [], alertes


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
    devise = ParametreSysteme.charger().devise_reference
    kpis = [
        _kpi('total', 'Total des demandes', len(de_l_annee), f"Depuis le 1er janvier {annee}", lien='/demandes?vue=toutes',
             icone='ri-stack-line'),
        _kpi('attente', 'En attente de validation', base.filter(statut=StatutDemande.EN_VALIDATION).count(), 'Tous circuits',
             lien='/demandes?vue=toutes&statut=en_validation', icone='ri-time-line'),
        _kpi('missions', 'Missions en cours', len(en_cours), "Collaborateurs en déplacement aujourd'hui", icone='ri-road-map-line'),
        _kpi('budget', 'Budget total approuvé', approuve, f"Année {annee}", 'montant', '/tableaux-de-bord?profil=direction',
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
    return kpis, listes, graphes, []


def finances(user):
    from missions.models import ClotureMission
    from tresorerie.models import Reglement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    annee = timezone.localdate().year
    a_payer = list(Demande.objects.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES)
                   .select_related('type_demande', 'demandeur').order_by('-approuvee_le'))
    approuvees = list(Demande.objects.filter(statut__in=APPROUVEES, approuvee_le__year=annee).select_related('type_demande', 'departement'))
    reglements = Reglement.objects.filter(annule=False).select_related('demande__type_demande', 'demande__demandeur').order_by('-date_paiement', '-id')
    clotures = ClotureMission.objects.filter(etat='soumise').count()
    devise = ParametreSysteme.charger().devise_reference
    kpis = [
        _kpi('approuve', 'Montant total approuvé', sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0')), f"Année {annee}",
             'montant', icone='ri-checkbox-circle-line'),
        _kpi('attente', 'En attente de paiement', sum((ref(d, d.solde or 0) for d in a_payer), Decimal('0')),
             f"{len(a_payer)} demande(s)", 'montant', '/tresorerie/a-payer', 'attention' if a_payer else '', 'ri-wallet-3-line'),
        _kpi('paye', 'Montant payé', reglements.filter(date_paiement__year=annee).aggregate(s=Sum('montant_ref'))['s'] or Decimal('0'),
             f"Année {annee}", 'montant', icone='ri-hand-coin-line'),
        _kpi('a_traiter', 'Demandes à traiter', len(a_payer) + clotures, f"{len(a_payer)} à payer · {clotures} clôture(s) à contrôler",
             lien='/tresorerie/a-payer', icone='ri-task-line'),
    ]
    par_dep = defaultdict(Decimal)
    for d in approuvees:
        par_dep[d.departement.libelle_service if d.departement_id else 'Non renseigné'] += ref(d, d.montant_approuve)
    graphes = [{'cle': 'departements', 'titre': f'Dépenses approuvées par département ({annee})', 'type': 'barres', 'unite': 'montant',
                'donnees': [{'libelle': l, 'valeur': str(v)} for l, v in sorted(par_dep.items(), key=lambda x: -x[1])[:8]]}]
    avec_fcm = (Demande.objects.filter(type_demande__famille='mission', demandes_rattachees__type_demande__code='FCM')
                .exclude(demandes_rattachees__statut__in=('brouillon', 'rejetee', 'annulee')).distinct()
                .select_related('type_demande', 'demandeur').order_by('-updated_at')[:5])
    listes = [
        _liste('a_payer', 'Demandes approuvées à payer', [_ligne(d, montant=str(ref(d, d.solde or 0)),
                                                                  info=f"Approuvée le {timezone.localtime(d.approuvee_le):%d/%m/%Y}" if d.approuvee_le else '')
                                                            for d in a_payer[:8]], '/tresorerie/a-payer', 'Aucune demande à payer.'),
        _liste('paiements', 'Paiements récents', [_ligne(r.demande, montant=str(r.montant_ref),
                                                         info=f"{r.get_mode_display()} le {r.date_paiement:%d/%m/%Y}") for r in reglements[:6]],
               None, 'Aucun paiement enregistré.'),
        _liste('fcm', 'Missions avec frais complémentaires', [_ligne(d) for d in avec_fcm], None, 'Aucune mission avec frais complémentaires.'),
    ]
    alertes = [{'ton': 'attention', 'texte': f"{clotures} clôture(s) de mission à contrôler.", 'lien': '/tresorerie/clotures'}] if clotures else []
    return kpis, listes, graphes, alertes


CALCULS = {'collaborateur': collaborateur, 'valideur': valideur, 'direction': direction, 'finances': finances}


def accueil(user, profil=None):
    disponibles = profils(user)
    profil = profil if profil in disponibles else disponibles[0]
    kpis, listes, graphes, alertes = CALCULS[profil](user)
    if profil != 'collaborateur':  # alertes personnelles toujours visibles
        alertes += collaborateur(user)[3]
    if profil != 'valideur' and 'valideur' in disponibles:
        alertes += valideur(user)[3]
    from notifications.models import Notification
    notifs = Notification.objects.filter(destinataire=user).order_by('-creee_le')[:5]
    activites = (Action.objects.filter(Q(demande__demandeur=user) | Q(auteur_reel=user))
                 .exclude(type__in=('creation',)).select_related('demande__type_demande', 'auteur_reel').order_by('-horodatage')[:8])
    roles = get_roles(user)
    actions = [{'libelle': 'Mission', 'icone': 'ri-road-map-line', 'lien': '/demandes/nouvelle', 'code': 'MLO'},
               {'libelle': 'Mission hors pays', 'icone': 'ri-flight-takeoff-line', 'lien': '/demandes/nouvelle', 'code': 'MHP'},
               {'libelle': 'Remboursement', 'icone': 'ri-refund-2-line', 'lien': '/demandes/nouvelle', 'code': 'RMB'},
               {'libelle': 'Autre demande', 'icone': 'ri-add-circle-line', 'lien': '/demandes/nouvelle', 'code': None}]
    raccourcis = [{'libelle': 'Mes demandes', 'icone': 'ri-file-list-3-line', 'lien': '/demandes'},
                  {'libelle': 'À valider', 'icone': 'ri-checkbox-multiple-line', 'lien': '/validations'},
                  {'libelle': 'Tableaux de bord', 'icone': 'ri-dashboard-3-line', 'lien': '/tableaux-de-bord'},
                  {'libelle': 'Délégations', 'icone': 'ri-user-shared-line', 'lien': '/delegations'}]
    if 'finances' in disponibles and (is_comptable(user) or is_admin_finances(user)):
        raccourcis.insert(2, {'libelle': 'À payer', 'icone': 'ri-wallet-3-line', 'lien': '/tresorerie/a-payer'})
    if is_admin(user) or roles & {'gestionnaire', 'admin_workflow', 'admin_finances'}:
        raccourcis.append({'libelle': 'Paramètres', 'icone': 'ri-settings-3-line', 'lien': '/parametres/accueil'})
    libelles = dict(PROFILS)
    return {
        'prenom': user.prenom or user.username, 'aujourdhui': timezone.localdate().isoformat(),
        'devise': ParametreSysteme.charger().devise_reference,
        'profils': [{'code': c, 'libelle': libelles[c]} for c in disponibles], 'profil': profil,
        'kpis': kpis, 'listes': listes, 'graphes': graphes, 'alertes': alertes,
        'actions_rapides': actions, 'raccourcis': raccourcis,
        'notifications': [{'id': n.pk, 'titre': n.titre, 'message': n.message, 'lien': n.lien, 'lue': n.lue,
                           'creee_le': n.creee_le.isoformat()} for n in notifs],
        'activites': [{'demande': a.demande_id, 'reference': a.demande.reference or 'Brouillon', 'type': a.get_type_display(),
                       'auteur': moteur.nom(a.auteur_reel) if a.auteur_reel_id else 'Système', 'motif': (a.motif or '')[:140],
                       'le': a.horodatage.isoformat()} for a in activites],
    }
