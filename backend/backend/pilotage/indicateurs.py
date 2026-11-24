"""
Tableaux de bord par profil (§14). Chaque tableau est décrit de façon générique
(indicateurs, barres, colonnes mensuelles, tableaux) : le web l'affiche et en
tire les exports Excel et PDF sans code propre à chaque tableau.
Montants agrégés en devise de référence (taux figés des demandes).
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from api import calendrier
from api.models import ParametreSysteme
from api.permissions import get_roles, is_admin, is_admin_finances, is_comptable
from demandes.models import Demande, StatutDemande
from workflow import moteur
from workflow.erreurs import ErreurMetier, Interdit
from workflow.models import Tache

EN_COURS = (StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER)
APPROUVEES = (StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE, StatutDemande.CLOTUREE)
MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']

PROFILS = [
    ('collaborateur', 'Mes demandes', 'ri-user-line'),
    ('valideur', 'Mes validations', 'ri-checkbox-multiple-line'),
    ('direction', 'Direction', 'ri-line-chart-line'),
    ('comptabilite', 'Comptabilité', 'ri-wallet-3-line'),
    ('administrateur', 'Administration', 'ri-settings-3-line'),
]


def profils_accessibles(user):
    roles = get_roles(user)
    acces = ['collaborateur', 'valideur']
    if is_admin(user) or roles & {'direction', 'controleur', 'admin_finances'}:
        acces.append('direction')
    if is_comptable(user) or is_admin_finances(user):
        acces.append('comptabilite')
    if is_admin(user):
        acces.append('administrateur')
    return [{'code': c, 'libelle': l, 'icone': i} for c, l, i in PROFILS if c in acces]


# ═══════════════════════════════════════════════════════════════
# OUTILS
# ═══════════════════════════════════════════════════════════════

def ref(d, montant):
    """Montant d'une demande en devise de référence, au taux figé de la demande."""
    if not montant:
        return Decimal('0')
    if d.devise == d.devise_reference or not d.montant_demande or not d.montant_demande_ref:
        return Decimal(montant)
    return (Decimal(montant) * d.montant_demande_ref / d.montant_demande).quantize(Decimal('0.01'))


def _date(params, cle, defaut):
    v = params.get(cle)
    if not v:
        return defaut
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ErreurMetier({cle: 'Date invalide (AAAA-MM-JJ).'})


def filtres(params):
    aujourd_hui = timezone.localdate()
    du = _date(params, 'du', date(aujourd_hui.year, 1, 1))
    au = _date(params, 'au', aujourd_hui)
    if au < du:
        raise ErreurMetier({'au': 'La fin de période précède le début.'})
    return {'du': du, 'au': au, **{k: params.get(k) for k in ('type_demande', 'statut', 'departement', 'agence',
                                                               'categorie', 'demandeur') if params.get(k)}}


def demandes(f, base=None):
    """Demandes soumises sur la période (date de soumission), filtres communs appliqués."""
    qs = (base if base is not None else Demande.objects.all()).filter(
        reference__isnull=False, soumise_le__date__gte=f['du'], soumise_le__date__lte=f['au'])
    for cle, champ in (('type_demande', 'type_demande_id'), ('departement', 'departement_id'), ('agence', 'agence_id'),
                       ('categorie', 'categorie_id'), ('demandeur', 'demandeur_id')):
        if f.get(cle):
            qs = qs.filter(**{champ: f[cle]})
    if f.get('statut'):
        qs = qs.filter(statut__in=str(f['statut']).split(','))
    return qs.select_related('type_demande', 'demandeur', 'departement', 'agence', 'categorie')


def mois_periode(f):
    mois, (a, m) = [], (f['du'].year, f['du'].month)
    while (a, m) <= (f['au'].year, f['au'].month) and len(mois) < 36:
        mois.append(f"{a}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return mois


def libelle_mois(cle):
    a, m = cle.split('-')
    return f"{MOIS[int(m) - 1]} {a[2:]}"


def ind(cle, libelle, valeur, format='nombre', aide='', lien=None, ton=''):
    return {'cle': cle, 'libelle': libelle, 'valeur': str(valeur) if isinstance(valeur, Decimal) else valeur,
            'format': format, 'aide': aide, 'lien': lien, 'ton': ton}


def barres(cle, titre, compteur, unite='montant', limite=12, aide=''):
    lignes = sorted(((l, v) for l, v in compteur.items() if v), key=lambda x: -x[1])
    if len(lignes) > limite:  # la fin de liste est regroupée en « Autres »
        autres = sum(v for _, v in lignes[limite - 1:])
        lignes = lignes[:limite - 1] + [('Autres', autres)]
    return {'cle': cle, 'titre': titre, 'type': 'barres', 'unite': unite, 'aide': aide,
            'donnees': [{'libelle': l or 'Non renseigné', 'valeur': str(v) if isinstance(v, Decimal) else v} for l, v in lignes]}


def colonnes(cle, titre, mois, series, valeurs, unite='montant'):
    return {'cle': cle, 'titre': titre, 'type': 'colonnes', 'unite': unite,
            'series': [{'cle': c, 'libelle': l} for c, l in series],
            'donnees': [{'libelle': libelle_mois(m), 'valeurs': {c: str(valeurs[m].get(c, 0)) for c, _ in series}} for m in mois]}


def tableau(cle, titre, cols, lignes, aide=''):
    return {'cle': cle, 'titre': titre, 'type': 'tableau', 'aide': aide,
            'colonnes': [{'cle': c, 'libelle': l, 'format': fmt} for c, l, fmt in cols],
            'lignes': [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in l.items()} for l in lignes]}


def _ligne_demande(d, **autres):
    return {'id': d.pk, 'reference': d.reference, 'type': d.type_demande.libelle, 'demandeur': moteur.nom(d.demandeur),
            'objet': d.objet, 'statut': d.get_statut_display(), **autres}


# ═══════════════════════════════════════════════════════════════
# PROFILS
# ═══════════════════════════════════════════════════════════════

def collaborateur(user, f):
    from tresorerie.models import Reversement
    toutes = Demande.objects.filter(demandeur=user)
    periode = list(demandes({**f, 'demandeur': user.pk}, toutes))
    compte = lambda *s: toutes.filter(statut__in=s).count()
    dus = Reversement.objects.filter(demande__demandeur=user, etat='a_percevoir')
    approuve = sum((ref(d, d.montant_approuve) for d in periode if d.statut in APPROUVEES), Decimal('0'))
    paye = sum((ref(d, d.montant_paye) for d in periode), Decimal('0'))
    indicateurs = [
        ind('brouillons', 'Brouillons', compte(StatutDemande.BROUILLON), lien='/demandes?statut=brouillon'),
        ind('en_validation', 'En validation', compte(StatutDemande.EN_VALIDATION), lien='/demandes?statut=en_validation'),
        ind('a_corriger', 'À corriger', compte(StatutDemande.A_CORRIGER), lien='/demandes?statut=a_corriger',
            ton='attention' if compte(StatutDemande.A_CORRIGER) else ''),
        ind('a_cloturer', 'Missions à clôturer', compte(StatutDemande.EN_ATTENTE_CLOTURE),
            lien='/demandes?statut=en_attente_cloture', ton='attention' if compte(StatutDemande.EN_ATTENTE_CLOTURE) else ''),
        ind('soumises', 'Demandes soumises sur la période', len(periode)),
        ind('approuve', 'Montant approuvé', approuve, 'montant'),
        ind('paye', 'Montant payé', paye, 'montant'),
        ind('reversements', 'Reversements dus', sum((r.montant_du for r in dus), Decimal('0')), 'montant',
            ton='alerte' if dus.exists() else ''),
    ]
    par_type, par_statut, mensuel = defaultdict(int), defaultdict(int), defaultdict(lambda: defaultdict(Decimal))
    for d in periode:
        par_type[d.type_demande.libelle] += 1
        par_statut[d.get_statut_display()] += 1
        m = f"{timezone.localtime(d.soumise_le):%Y-%m}"
        mensuel[m]['demande'] += ref(d, d.montant_demande)
        mensuel[m]['approuve'] += ref(d, d.montant_approuve) if d.statut in APPROUVEES else 0
    missions = [d for d in periode if d.type_demande.famille == 'mission']
    sections = [
        barres('par_statut', 'Mes demandes par statut', par_statut, 'nombre'),
        barres('par_type', 'Mes demandes par type', par_type, 'nombre'),
        colonnes('mensuel', 'Montants demandés et approuvés par mois', mois_periode(f),
                 [('demande', 'Demandé'), ('approuve', 'Approuvé')], mensuel),
        tableau('missions', 'Historique de mes missions',
                [('reference', 'Référence', 'texte'), ('destination', 'Destination', 'texte'), ('depart', 'Départ', 'date'),
                 ('retour', 'Retour', 'date'), ('statut', 'Statut', 'texte'), ('approuve', 'Approuvé', 'montant'),
                 ('paye', 'Payé', 'montant')],
                [_ligne_demande(d, destination=(d.donnees.get('mission') or {}).get('ville_destination_libelle', ''),
                                depart=str((d.donnees.get('mission') or {}).get('depart_le', ''))[:10],
                                retour=str((d.donnees.get('mission') or {}).get('retour_le', ''))[:10],
                                approuve=ref(d, d.montant_approuve), paye=ref(d, d.montant_paye)) for d in missions]),
        tableau('reversements', 'Reversements à effectuer',
                [('reference', 'Demande', 'texte'), ('origine', 'Origine', 'texte'), ('montant', 'Montant dû', 'montant'),
                 ('depuis', 'Depuis le', 'date')],
                [{'id': r.demande_id, 'reference': r.demande.reference, 'origine': r.get_origine_display(),
                  'montant': r.montant_du, 'depuis': f"{timezone.localtime(r.cree_le):%Y-%m-%d}"}
                 for r in dus.select_related('demande')]),
    ]
    return indicateurs, sections


def valideur(user, f):
    ctx = calendrier._contexte()
    maintenant = timezone.now()
    en_attente = list(Tache.objects.filter(etat='en_attente').filter(moteur.filtre_taches_de(user))
                      .select_related('etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                                      'etape_instance__instance__demande__demandeur'))
    faites = list(Tache.objects.filter(traitee_par=user, etat='faite', traitee_le__date__gte=f['du'],
                                       traitee_le__date__lte=f['au'])
                  .select_related('etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                                  'etape_instance__instance__demande__departement',
                                  'etape_instance__instance__demande__demandeur').order_by('-traitee_le'))
    if f.get('type_demande'):
        faites = [t for t in faites if str(t.etape_instance.instance.demande.type_demande_id) == str(f['type_demande'])]
        en_attente = [t for t in en_attente if str(t.etape_instance.instance.demande.type_demande_id) == str(f['type_demande'])]
    retard = [t for t in en_attente if t.echeance and t.echeance < maintenant]
    delais = [calendrier.heures_ouvrees(t.ouverte_le, t.traitee_le, ctx) for t in faites if t.ouverte_le and t.traitee_le]
    decisions = defaultdict(int)
    for t in faites:
        decisions[t.decision] += 1
    indicateurs = [
        ind('a_traiter', 'À traiter', len(en_attente), lien='/validations', ton='attention' if en_attente else ''),
        ind('en_retard', 'En retard', len(retard), ton='alerte' if retard else ''),
        ind('traitees', 'Traitées sur la période', len(faites)),
        ind('approuvees', 'Approuvées', decisions['approuvee']),
        ind('retournees', 'Retournées', decisions['retournee']),
        ind('rejetees', 'Rejetées', decisions['rejetee']),
        ind('delai', 'Délai moyen de traitement', round(sum(delais) / len(delais), 1) if delais else 0, 'heures',
            aide='Heures ouvrées entre l\'ouverture de l\'étape et la décision'),
    ]
    par_dep, par_type = defaultdict(int), defaultdict(int)
    for t in faites:
        d = t.etape_instance.instance.demande
        par_dep[d.departement.libelle_service if d.departement_id else ''] += 1
        par_type[d.type_demande.libelle] += 1
    libelles = {'approuvee': 'Approuvée', 'rejetee': 'Rejetée', 'retournee': 'Retournée'}
    sections = [
        tableau('a_traiter', 'Validations à traiter',
                [('reference', 'Demande', 'texte'), ('demandeur', 'Demandeur', 'texte'), ('etape', 'Étape', 'texte'),
                 ('ouverte', 'Ouverte le', 'dateheure'), ('echeance', 'Échéance', 'dateheure'), ('retard', 'En retard', 'oui_non')],
                [{'id': t.etape_instance.instance.demande_id, 'reference': t.etape_instance.instance.demande.reference,
                  'demandeur': moteur.nom(t.etape_instance.instance.demande.demandeur), 'etape': t.etape_instance.etape.libelle,
                  'ouverte': t.ouverte_le.isoformat() if t.ouverte_le else None,
                  'echeance': t.echeance.isoformat() if t.echeance else None, 'retard': t in retard} for t in en_attente]),
        barres('par_departement', 'Validations par département du demandeur', par_dep, 'nombre'),
        barres('par_type', 'Validations par type de demande', par_type, 'nombre'),
        tableau('historique', 'Historique de mes validations',
                [('reference', 'Demande', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('etape', 'Étape', 'texte'), ('decision', 'Décision', 'texte'), ('le', 'Le', 'dateheure')],
                [{'id': t.etape_instance.instance.demande_id, 'reference': t.etape_instance.instance.demande.reference,
                  'type': t.etape_instance.instance.demande.type_demande.libelle,
                  'demandeur': moteur.nom(t.etape_instance.instance.demande.demandeur), 'etape': t.etape_instance.etape.libelle,
                  'decision': libelles.get(t.decision, t.decision), 'le': t.traitee_le.isoformat()} for t in faites[:200]]),
    ]
    return indicateurs, sections


def direction(user, f):
    from tresorerie.models import Reversement
    periode = list(demandes(f).exclude(statut=StatutDemande.ANNULEE) if not f.get('statut') else demandes(f))
    approuvees = [d for d in periode if d.statut in APPROUVEES]
    missions = [d for d in periode if d.type_demande.famille == 'mission']
    tm = lambda d: (d.type_demande.parametres or {}).get('type_mission')
    engagements = sum((ref(d, d.solde or 0) for d in approuvees if d.statut != StatutDemande.CLOTUREE), Decimal('0'))
    delais = [(d.approuvee_le - d.soumise_le).total_seconds() / 86400 for d in approuvees if d.approuvee_le and d.soumise_le]
    indicateurs = [
        ind('soumises', 'Demandes soumises', len(periode)),
        ind('missions', 'Missions', len(missions)),
        ind('locales', 'dont locales', sum(1 for d in missions if tm(d) == 'locale')),
        ind('hors_pays', 'dont hors pays', sum(1 for d in missions if tm(d) == 'hors_pays')),
        ind('demande', 'Montant demandé', sum((d.montant_demande_ref or ref(d, d.montant_demande) for d in periode), Decimal('0')), 'montant'),
        ind('approuve', 'Montant approuvé', sum((ref(d, d.montant_approuve) for d in approuvees), Decimal('0')), 'montant'),
        ind('paye', 'Montant payé', sum((ref(d, d.montant_paye) for d in periode), Decimal('0')), 'montant'),
        ind('engagements', 'Engagements (approuvé non payé)', engagements, 'montant'),
        ind('reversements', 'Reversements à percevoir', Reversement.objects.filter(
            etat='a_percevoir', demande__in=[d.pk for d in periode]).aggregate(s=Sum('montant_du'))['s'] or Decimal('0'), 'montant'),
        ind('delai', "Délai moyen d'approbation", round(sum(delais) / len(delais), 1) if delais else 0, 'jours'),
    ]
    par = {k: defaultdict(Decimal) for k in ('dep', 'cat', 'agence', 'type')}
    mensuel, villes = defaultdict(lambda: defaultdict(Decimal)), defaultdict(int)
    for d in approuvees:
        v = ref(d, d.montant_approuve)
        par['dep'][d.departement.libelle_service if d.departement_id else ''] += v
        par['cat'][d.categorie.libelle if d.categorie_id else ''] += v
        par['agence'][d.agence.nom_agence if d.agence_id else ''] += v
        par['type'][d.type_demande.libelle] += v
    for d in periode:
        m = f"{timezone.localtime(d.soumise_le):%Y-%m}"
        mensuel[m]['demande'] += d.montant_demande_ref or ref(d, d.montant_demande)
        if d.statut in APPROUVEES:
            mensuel[m]['approuve'] += ref(d, d.montant_approuve)
        mensuel[m]['paye'] += ref(d, d.montant_paye)
    for d in missions:
        villes[(d.donnees.get('mission') or {}).get('ville_destination_libelle', '')] += 1
    sections = [
        colonnes('mensuel', 'Montants demandés, approuvés et payés par mois de soumission', mois_periode(f),
                 [('demande', 'Demandé'), ('approuve', 'Approuvé'), ('paye', 'Payé')], mensuel),
        barres('par_departement', 'Montant approuvé par département', par['dep']),
        barres('par_categorie', 'Montant approuvé par catégorie de salarié', par['cat']),
        barres('par_agence', 'Montant approuvé par agence', par['agence']),
        barres('par_type', 'Montant approuvé par type de demande', par['type']),
        barres('destinations', 'Missions par destination', villes, 'nombre', limite=10),
        tableau('engagements', 'Engagements : demandes approuvées restant à payer',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('approuve', 'Approuvé', 'montant'), ('reste', 'Reste à payer', 'montant')],
                sorted([_ligne_demande(d, approuve=ref(d, d.montant_approuve), reste=ref(d, d.solde or 0))
                        for d in approuvees if d.statut != StatutDemande.CLOTUREE and (d.solde or 0) > 0],
                       key=lambda l: -Decimal(l['reste']))[:100]),
    ]
    return indicateurs, sections


def comptabilite(user, f):
    from tresorerie.models import Reglement, Reversement
    from tresorerie.services import FINANCIERS_PAYABLES, STATUTS_PAYABLES
    a_payer = list(Demande.objects.filter(statut__in=STATUTS_PAYABLES, statut_financier__in=FINANCIERS_PAYABLES)
                   .select_related('type_demande', 'demandeur').order_by('approuvee_le'))
    if f.get('type_demande'):
        a_payer = [d for d in a_payer if str(d.type_demande_id) == str(f['type_demande'])]
    reglements = list(Reglement.objects.filter(annule=False, date_paiement__gte=f['du'], date_paiement__lte=f['au'])
                      .select_related('demande__type_demande', 'demande__demandeur', 'enregistre_par').order_by('-date_paiement'))
    a_percevoir = Reversement.objects.filter(etat='a_percevoir')
    percus = Reversement.objects.filter(etat='percu', percu_le__gte=f['du'], percu_le__lte=f['au'])
    paye = lambda r: r.montant_ref
    indicateurs = [
        ind('a_payer', 'Demandes à payer', len(a_payer), lien='/tresorerie/a-payer', ton='attention' if a_payer else ''),
        ind('reste', 'Reste à payer', sum((ref(d, d.solde or 0) for d in a_payer), Decimal('0')), 'montant'),
        ind('partielles', 'Partiellement payées', sum(1 for d in a_payer if d.statut_financier == 'partiellement_payee')),
        ind('paye', 'Payé sur la période', sum((paye(r) for r in reglements), Decimal('0')), 'montant'),
        ind('reglements', 'Règlements sur la période', len(reglements)),
        ind('a_percevoir', 'Reversements à percevoir', a_percevoir.aggregate(s=Sum('montant_du'))['s'] or Decimal('0'), 'montant',
            lien='/tresorerie/reversements', ton='alerte' if a_percevoir.exists() else ''),
        ind('percus', 'Reversements perçus sur la période', percus.aggregate(s=Sum('montant_du'))['s'] or Decimal('0'), 'montant'),
    ]
    par_mode, mensuel = defaultdict(Decimal), defaultdict(lambda: defaultdict(Decimal))
    for r in reglements:
        par_mode[r.get_mode_display()] += paye(r)
        mensuel[f"{r.date_paiement:%Y-%m}"]['paye'] += paye(r)
    for r in percus:
        mensuel[f"{r.percu_le:%Y-%m}"]['reverse'] += r.montant_du
    aujourd_hui = timezone.localdate()
    sections = [
        colonnes('mensuel', 'Paiements et reversements perçus par mois', mois_periode(f),
                 [('paye', 'Payé'), ('reverse', 'Reversé')], mensuel),
        barres('par_mode', 'Paiements par mode', par_mode),
        tableau('anciennes', 'Demandes à payer, les plus anciennes',
                [('reference', 'Référence', 'texte'), ('type', 'Type', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('approuvee', 'Approuvée le', 'date'), ('jours', 'Attente (jours)', 'nombre'), ('reste', 'Reste à payer', 'montant')],
                [_ligne_demande(d, approuvee=f"{timezone.localtime(d.approuvee_le):%Y-%m-%d}" if d.approuvee_le else None,
                                jours=(aujourd_hui - timezone.localtime(d.approuvee_le).date()).days if d.approuvee_le else None,
                                reste=ref(d, d.solde or 0)) for d in a_payer[:30]]),
        tableau('reglements', 'Historique des règlements',
                [('date', 'Date', 'date'), ('reference', 'Demande', 'texte'), ('demandeur', 'Demandeur', 'texte'),
                 ('mode', 'Mode', 'texte'), ('ref_paiement', 'Référence', 'texte'), ('montant', 'Montant', 'montant')],
                [{'id': r.demande_id, 'date': r.date_paiement.isoformat(), 'reference': r.demande.reference,
                  'demandeur': moteur.nom(r.demande.demandeur), 'mode': r.get_mode_display(), 'ref_paiement': r.reference,
                  'montant': r.montant_ref} for r in reglements[:300]]),
    ]
    return indicateurs, sections


def administrateur(user, f):
    from api import organisation as org
    from api.models import Responsabilite, Service
    from audit.models import JournalActivite
    from demandes.models import TypeDemande
    from workflow.models import VersionWorkflow
    User = get_user_model()
    journal = JournalActivite.objects.filter(horodatage__date__gte=f['du'], horodatage__date__lte=f['au'])
    sans_titulaire = [r for r in Responsabilite.objects.filter(actif=True, portee='globale') if not org.titulaires(r)]
    types_sans = [t for t in TypeDemande.objects.filter(actif=True) if not moteur.version_publiee(t)]
    baremes = journal.filter(action__startswith='bareme.')
    indicateurs = [
        ind('actifs', 'Comptes actifs', User.objects.filter(is_active=True).count(), lien='/parametres/user'),
        ind('inactifs', 'Comptes désactivés', User.objects.filter(is_active=False).count()),
        ind('departements', 'Départements', Service.objects.count(), lien='/parametres/departement'),
        ind('sans_titulaire', 'Responsabilités sans titulaire', len(sans_titulaire), lien='/parametres/responsabilite',
            ton='alerte' if sans_titulaire else ''),
        ind('types', 'Types de demande actifs', TypeDemande.objects.filter(actif=True).count()),
        ind('circuits', 'Circuits publiés', VersionWorkflow.objects.filter(etat='publiee').count(), lien='/parametres/workflows'),
        ind('brouillons', 'Versions de circuit en brouillon', VersionWorkflow.objects.filter(etat='brouillon').count()),
        ind('baremes', 'Changements de barèmes sur la période', baremes.count(), lien='/parametres/baremes'),
        ind('journal', 'Opérations journalisées sur la période', journal.count(), lien='/parametres/journal'),
    ]
    par_role, par_action = defaultdict(int), defaultdict(int)
    from api.permissions import LIBELLES_ROLES
    for nom_groupe, n in User.objects.filter(is_active=True).values_list('groups__name').annotate(n=Count('id')):
        if nom_groupe:
            par_role[LIBELLES_ROLES.get(nom_groupe, nom_groupe)] += n
    for a in journal.values_list('action', flat=True):
        par_action[a] += 1
    sections = [
        barres('par_role', 'Comptes actifs par rôle', par_role, 'nombre'),
        barres('journal', "Opérations du journal d'activité par type", par_action, 'nombre'),
        tableau('sans_titulaire', 'Responsabilités sans titulaire',
                [('code', 'Code', 'texte'), ('libelle', 'Responsabilité', 'texte')],
                [{'code': r.code, 'libelle': r.libelle} for r in sans_titulaire]),
        tableau('types_sans_circuit', 'Types de demande sans circuit publié',
                [('code', 'Code', 'texte'), ('libelle', 'Type', 'texte')], [{'code': t.code, 'libelle': t.libelle} for t in types_sans]),
        tableau('baremes', 'Derniers changements de barèmes',
                [('le', 'Le', 'dateheure'), ('auteur', 'Auteur', 'texte'), ('objet', 'Barème', 'texte'), ('motif', 'Motif', 'texte')],
                [{'le': j.horodatage.isoformat(), 'auteur': moteur.nom(j.auteur) if j.auteur_id else 'Système',
                  'objet': j.objet_libelle, 'motif': j.motif} for j in baremes.select_related('auteur').order_by('-horodatage')[:50]]),
    ]
    return indicateurs, sections


CALCULS = {'collaborateur': collaborateur, 'valideur': valideur, 'direction': direction, 'comptabilite': comptabilite,
           'administrateur': administrateur}


def tableau_de_bord(user, profil, params):
    acces = {p['code']: p for p in profils_accessibles(user)}
    if profil not in acces:
        raise Interdit("Ce tableau de bord ne vous est pas accessible.")
    f = filtres(params)
    indicateurs, sections = CALCULS[profil](user, f)
    return {'profil': profil, 'titre': acces[profil]['libelle'], 'devise': ParametreSysteme.charger().devise_reference,
            'du': f['du'].isoformat(), 'au': f['au'].isoformat(), 'genere_le': timezone.now().isoformat(),
            'indicateurs': indicateurs, 'sections': sections}
