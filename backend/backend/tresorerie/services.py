"""
Services de trésorerie (§8) : statut financier, règlements, reversements,
clôture automatique (mode A). Seule porte d'entrée pour les mouvements
d'argent d'une demande.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from api.permissions import is_admin_finances, is_comptable
from demandes.models import Demande, StatutDemande, StatutFinancier, TypePiece
from notifications.services import notifier
from workflow import moteur
from workflow.erreurs import ErreurMetier, Interdit
from workflow.models import Tache

from .models import MODES_PAIEMENT, Reglement, Reversement

STATUTS_PAYABLES = {StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE}
FINANCIERS_PAYABLES = {StatutFinancier.A_PAYER, StatutFinancier.PARTIELLEMENT_PAYEE}


def _montant(brut, nom='montant'):
    try:
        v = Decimal(str(brut).replace(' ', '').replace(',', '.')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError, TypeError):
        raise ErreurMetier({nom: 'Montant invalide.'})
    if v <= 0:
        raise ErreurMetier({nom: 'Le montant doit être positif.'})
    return v


def _date(brute, nom):
    if not brute:
        return timezone.localdate()
    try:
        d = date.fromisoformat(str(brute)[:10])
    except ValueError:
        raise ErreurMetier({nom: 'Date invalide.'})
    if d > timezone.localdate():
        raise ErreurMetier({nom: 'La date ne peut pas être dans le futur.'})
    return d


def fmt(montant, devise=''):
    """1 500 000 XOF (espace insécable entre les milliers, centimes seulement s'il y en a)."""
    m = Decimal(str(montant or 0))
    texte = f"{m:,.0f}" if m == m.to_integral() else f"{m:,.2f}"
    texte = texte.replace(',', '\u00a0').replace('.', ',')
    return f"{texte} {devise}".strip()


def comptables():
    User = get_user_model()
    return list(User.objects.filter(is_active=True, groups__name='comptable').distinct())


# ═══════════════════════════════════════════════════════════════
# STATUT FINANCIER ET CLÔTURE AUTOMATIQUE
# ═══════════════════════════════════════════════════════════════

def statut_financier(demande):
    """Statut financier déduit des montants et des reversements (§4.2)."""
    if demande.reversements.filter(etat='a_percevoir').exists():
        return StatutFinancier.REVERSEMENT_ATTENDU
    paye, approuve = demande.montant_paye or Decimal('0'), demande.montant_du or Decimal('0')
    if demande.statut == StatutDemande.ANNULEE:
        return StatutFinancier.SOLDEE if paye > 0 or demande.reversements.exists() else StatutFinancier.SANS_OBJET
    if demande.statut not in STATUTS_PAYABLES | {StatutDemande.CLOTUREE}:
        return StatutFinancier.SANS_OBJET
    if approuve <= 0:
        return StatutFinancier.SANS_OBJET
    if paye <= 0:
        return StatutFinancier.A_PAYER
    if paye < approuve:
        return StatutFinancier.PARTIELLEMENT_PAYEE
    return StatutFinancier.SOLDEE if demande.statut == StatutDemande.CLOTUREE else StatutFinancier.PAYEE


def mettre_a_jour(demande, user=None, infos=None):
    """Recalcule le statut financier ; mode de clôture A : clôture dès que la demande est payée."""
    demande.statut_financier = statut_financier(demande)
    regle = StatutFinancier.PAYEE, StatutFinancier.SANS_OBJET
    if (demande.statut == StatutDemande.APPROUVEE and demande.type_demande.mode_cloture == 'automatique'
            and demande.statut_financier in regle):
        demande.statut, demande.cloturee_le = StatutDemande.CLOTUREE, timezone.now()
        demande.statut_financier = statut_financier(demande)
        moteur.tracer(demande, 'cloture', auteur=user, infos=infos,
                      motif='Clôture automatique : demande payée.' if (demande.montant_approuve or 0) > 0
                      else 'Clôture automatique : demande sans montant.')
    elif demande.statut == StatutDemande.EN_ATTENTE_CLOTURE and demande.statut_financier in regle:
        # Mode B (§9) : éléments de clôture validés, demande payée, aucun reversement à percevoir
        from missions.models import ClotureMission
        if ClotureMission.objects.filter(demande=demande, etat='validee').exists() or (
                demande.type_demande.famille != 'mission' and demande.montant_retenu is not None):
            demande.statut, demande.cloturee_le = StatutDemande.CLOTUREE, timezone.now()
            demande.statut_financier = statut_financier(demande)
            moteur.tracer(demande, 'cloture', auteur=user, infos=infos,
                          motif='Demande clôturée : éléments de clôture validés, paiements soldés.')
    demande.save(update_fields=['statut', 'statut_financier', 'cloturee_le', 'montant_paye', 'montant_reverse',
                                'montant_retenu', 'updated_at'])
    return demande


# ═══════════════════════════════════════════════════════════════
# RÈGLEMENTS
# ═══════════════════════════════════════════════════════════════

def annulation_en_cours(demande):
    return Demande.objects.filter(demande_parent=demande, type_demande__famille='annulation', statut__in=(
        StatutDemande.BROUILLON, StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER)).first()


def peut_payer(demande, user):
    return (is_comptable(user) and demande.statut in STATUTS_PAYABLES
            and demande.statut_financier in FINANCIERS_PAYABLES)


def enregistrer_reglement(demande, user, montant, date_paiement=None, mode='virement', reference='',
                          beneficiaire='', fichier=None, infos=None):
    from baremes import services as baremes
    from demandes.services import creer_document
    if not is_comptable(user):
        raise Interdit("Les paiements sont enregistrés par la comptabilité.")
    with transaction.atomic():
        demande = Demande.objects.select_for_update().select_related('type_demande', 'demandeur').get(pk=demande.pk)
        if demande.statut not in STATUTS_PAYABLES or demande.statut_financier not in FINANCIERS_PAYABLES:
            raise ErreurMetier(f"Cette demande n'est pas à payer ({demande.get_statut_financier_display().lower()}).")
        ann = annulation_en_cours(demande)
        if ann is not None:
            raise ErreurMetier(f"Une demande d'annulation est en cours ({ann.reference or 'brouillon'}) : "
                               "paiement suspendu.")
        td = demande.type_demande
        if td.separation_approbation_paiement and Tache.objects.filter(
                etape_instance__instance__demande=demande, traitee_par=user, decision='approuvee').exists():
            raise Interdit("Séparation des tâches : vous avez approuvé cette demande, un autre comptable doit la payer.")
        montant = _montant(montant)
        solde = demande.solde
        if montant > solde:
            raise ErreurMetier({'montant': f"Le montant dépasse le reste à payer ({fmt(solde, demande.devise)})."})
        if not td.paiement_fractionne_autorise and montant != solde:
            raise ErreurMetier({'montant': f"Ce type de demande se paie en une fois : {fmt(solde, demande.devise)}."})
        if mode not in dict(MODES_PAIEMENT):
            raise ErreurMetier({'mode': 'Mode de paiement inconnu.'})
        d = _date(date_paiement, 'date_paiement')
        if td.exigences.filter(moment='paiement', obligatoire=True).exists() and fichier is None:
            raise ErreurMetier({'justificatif': 'Le justificatif de paiement est obligatoire pour ce type de demande.'})
        ref = demande.devise_reference or baremes.devise_reference()
        t = (demande.parametres_figes or {}).get('taux', {}).get(demande.devise) if demande.devise != ref else None
        t = t or baremes.taux(demande.devise, d, ref)
        if t is None:
            raise ErreurMetier({'montant': f"Aucun taux de change pour {demande.devise}."})
        justificatif = None
        if fichier is not None:
            justificatif = creer_document(demande, user, fichier,
                                          TypePiece.objects.filter(code='justificatif_paiement').first())
        r = Reglement.objects.create(
            demande=demande, montant=montant, devise=demande.devise, taux_change=Decimal(t['taux']),
            montant_ref=baremes.convertir(montant, t), date_paiement=d, mode=mode, reference=(reference or '')[:100],
            beneficiaire=(beneficiaire or moteur.nom(demande.demandeur))[:255], justificatif=justificatif,
            enregistre_par=user)
        demande.montant_paye = (demande.montant_paye or 0) + montant
        moteur.tracer(demande, 'paiement', auteur=user, infos=infos,
                      motif=f"Paiement de {fmt(montant, demande.devise)} ({r.get_mode_display().lower()}"
                            f"{', réf. ' + r.reference if r.reference else ''}).",
                      donnees={'reglement': r.pk})
        mettre_a_jour(demande, user, infos)
        reste = demande.solde
        notifier([demande.demandeur], 'paiement', f"{demande.reference} : paiement effectué",
                 f"{fmt(montant, demande.devise)} ont été payés" + (f" ; reste {fmt(reste, demande.devise)}." if reste else "."),
                 demande)
    return r


def annuler_reglement(reglement, user, motif, infos=None):
    """Erreur de saisie : annulation motivée par un administrateur des finances (le règlement reste tracé)."""
    if not is_admin_finances(user):
        raise Interdit("L'annulation d'un paiement est réservée aux administrateurs des finances.")
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier({'motif': "Le motif d'annulation est obligatoire."})
    with transaction.atomic():
        r = Reglement.objects.select_for_update().get(pk=reglement.pk)
        if r.annule:
            raise ErreurMetier("Ce paiement est déjà annulé.")
        demande = Demande.objects.select_for_update().get(pk=r.demande_id)
        if demande.statut == StatutDemande.ANNULEE:
            raise ErreurMetier("La demande est annulée : régularisez par le reversement.")
        r.annule, r.annule_par, r.annule_le, r.motif_annulation = True, user, timezone.now(), motif
        r.save()
        demande.montant_paye -= r.montant
        if demande.statut == StatutDemande.CLOTUREE and demande.type_demande.mode_cloture == 'automatique':
            demande.statut, demande.cloturee_le = StatutDemande.APPROUVEE, None  # rouverte : de nouveau à payer
        moteur.tracer(demande, 'paiement_annule', auteur=user, infos=infos, motif=f"Paiement de {fmt(r.montant, r.devise)} du {r.date_paiement:%d/%m/%Y} annulé : {motif}",
                      donnees={'reglement': r.pk})
        mettre_a_jour(demande, user, infos)
    return r


# ═══════════════════════════════════════════════════════════════
# REVERSEMENTS
# ═══════════════════════════════════════════════════════════════

def creer_reversement(demande, montant, origine, motif, user=None, infos=None):
    """Somme à rendre par le demandeur (annulation après paiement, clôture)."""
    r = Reversement.objects.create(demande=demande, montant_du=montant, devise=demande.devise, origine=origine,
                                   motif=motif)
    moteur.tracer(demande, 'reversement', auteur=user, infos=infos,
                  motif=f"Reversement attendu : {fmt(montant, demande.devise)} ({r.get_origine_display().lower()}).",
                  donnees={'reversement': r.pk})
    notifier([demande.demandeur], 'reversement', f"{demande.reference} : reversement à effectuer",
             f"Vous devez reverser {fmt(montant, demande.devise)} à la société ({motif}).", demande)
    notifier(comptables(), 'reversement', f"{demande.reference} : reversement à percevoir",
             f"{fmt(montant, demande.devise)} à percevoir de {moteur.nom(demande.demandeur)}.", demande)
    return r


def percevoir(reversement, user, date_perception=None, mode='virement', reference='', fichier=None, infos=None):
    from demandes.services import creer_document
    if not is_comptable(user):
        raise Interdit("La perception d'un reversement est enregistrée par la comptabilité.")
    with transaction.atomic():
        r = Reversement.objects.select_for_update().get(pk=reversement.pk)
        if r.etat != 'a_percevoir':
            raise ErreurMetier("Ce reversement est déjà traité.")
        if mode not in dict(MODES_PAIEMENT):
            raise ErreurMetier({'mode': 'Mode de paiement inconnu.'})
        demande = Demande.objects.select_for_update().get(pk=r.demande_id)
        if fichier is not None:
            r.justificatif = creer_document(demande, user, fichier,
                                            TypePiece.objects.filter(code='justificatif_paiement').first())
        r.etat, r.percu_le, r.mode, r.reference = 'percu', _date(date_perception, 'percu_le'), mode, (reference or '')[:100]
        r.traite_par, r.traite_le = user, timezone.now()
        r.save()
        demande.montant_reverse = (demande.montant_reverse or 0) + r.montant_du
        moteur.tracer(demande, 'reversement', auteur=user, infos=infos,
                      motif=f"Reversement de {fmt(r.montant_du, r.devise)} perçu le {r.percu_le:%d/%m/%Y}.",
                      donnees={'reversement': r.pk})
        mettre_a_jour(demande, user, infos)
        notifier([demande.demandeur], 'reversement', f"{demande.reference} : reversement reçu",
                 f"Votre reversement de {fmt(r.montant_du, r.devise)} est enregistré.", demande)
    return r


def abandonner(reversement, user, motif, infos=None):
    if not is_admin_finances(user):
        raise Interdit("L'abandon d'un reversement est réservé aux administrateurs des finances.")
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier({'motif': "Le motif de l'abandon est obligatoire."})
    with transaction.atomic():
        r = Reversement.objects.select_for_update().get(pk=reversement.pk)
        if r.etat != 'a_percevoir':
            raise ErreurMetier("Ce reversement est déjà traité.")
        demande = Demande.objects.select_for_update().get(pk=r.demande_id)
        if demande.demandeur_id == user.pk:
            raise Interdit("Vous ne pouvez pas abandonner un reversement qui vous concerne.")
        r.etat, r.motif_abandon, r.traite_par, r.traite_le = 'abandonne', motif, user, timezone.now()
        r.save()
        moteur.tracer(demande, 'reversement', auteur=user, infos=infos,
                      motif=f"Reversement de {fmt(r.montant_du, r.devise)} abandonné : {motif}", donnees={'reversement': r.pk})
        mettre_a_jour(demande, user, infos)
    return r


# ═══════════════════════════════════════════════════════════════
# ANNULATION APRÈS APPROBATION (§4.3)
# ═══════════════════════════════════════════════════════════════

STATUTS_ANNULABLES = {StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER, StatutDemande.APPROUVEE,
                      StatutDemande.EN_ATTENTE_CLOTURE, StatutDemande.CLOTUREE}


def annuler_definitivement(demande, motif, origine, auteur=None, infos=None, donnees=None, _cascade=True):
    """
    Annulation d'une demande soumise, quel que soit son stade (§4.3, décisions 1, 2 et 5) :
    circuit en cours arrêté, reversement du montant payé, demandes rattachées encore
    actives (frais complémentaires, demande d'annulation en cours) annulées aussi.
    `origine` : texte de l'historique (« par la demande ANN-… », « par l'administrateur … »).
    """
    demande = Demande.objects.select_for_update().get(pk=demande.pk)
    if demande.statut not in STATUTS_ANNULABLES:
        return demande
    instance = demande.instances.filter(etat='en_cours').first()
    if instance:
        moteur.annuler_instance(instance, auteur, motif, infos)
    demande.statut, demande.annulee_le, demande.motif_annulation = StatutDemande.ANNULEE, timezone.now(), motif
    demande.save(update_fields=['statut', 'annulee_le', 'motif_annulation', 'updated_at'])
    moteur.tracer(demande, 'annulation', auteur=auteur, infos=infos, instance=instance,
                  motif=f"Annulée {origine} : {motif}", donnees=donnees)
    du = (demande.montant_paye or 0) - (demande.montant_reverse or 0) - sum(
        r.montant_du for r in demande.reversements.filter(etat='a_percevoir'))
    if du > 0:
        creer_reversement(demande, du, 'annulation', f"Annulation après paiement ({origine})", infos=infos)
    mettre_a_jour(demande, infos=infos)
    notifier([demande.demandeur], 'demande_annulee', f"{demande.reference} annulée", f"Votre demande est annulée {origine}.",
             demande)
    if _cascade:
        filles = (Demande.objects.filter(demande_parent=demande)
                  .exclude(statut__in=(StatutDemande.REJETEE, StatutDemande.ANNULEE))
                  .exclude(type_demande__famille='annulation', statut=StatutDemande.CLOTUREE))
        for fille in filles:  # frais complémentaires (même payés et clôturés), annulation en cours
            if fille.statut == StatutDemande.BROUILLON:
                fille.statut, fille.annulee_le = StatutDemande.ANNULEE, timezone.now()
                fille.motif_annulation = f"Demande d'origine {demande.reference} annulée"
                fille.save(update_fields=['statut', 'annulee_le', 'motif_annulation', 'updated_at'])
                continue
            annuler_definitivement(fille, f"Demande d'origine {demande.reference} annulée", 'automatiquement',
                                   auteur, infos, _cascade=False)
    return demande


def annuler_apres_approbation(demande, annulation, infos=None):
    """La demande d'annulation `annulation` est approuvée : la demande initiale est annulée."""
    motif = (annulation.donnees or {}).get('motif') or annulation.objet
    annuler_definitivement(demande, f"{annulation.reference} : {motif}", f"par la demande {annulation.reference}",
                           infos=infos, donnees={'demande_annulation': annulation.pk})


def annuler_par_administrateur(demande, admin, motif, infos=None):
    """Décision 1 : un administrateur annule la demande d'un collaborateur (absence, doublon, départ)."""
    from api.permissions import is_admin
    if not is_admin(admin):
        raise Interdit("Réservé aux administrateurs.")
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier({'motif': "Le motif est obligatoire."})
    if demande.statut not in STATUTS_ANNULABLES:
        raise ErreurMetier(f"Une demande « {demande.get_statut_display()} » ne peut pas être annulée.")
    with transaction.atomic():
        return annuler_definitivement(demande, motif, f"par l'administrateur {moteur.nom(admin)}", admin, infos)


def synthese(demande):
    """Mission et frais complémentaires approuvés : engagé, payé, solde (§6)."""
    complements = Demande.objects.filter(demande_parent=demande, type_demande__parametres__complement=True)
    retenus = complements.filter(statut__in=(StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE,
                                             StatutDemande.CLOTUREE))
    agg = retenus.aggregate(approuve=Sum('montant_approuve'), paye=Sum('montant_paye'))
    engage = (demande.montant_approuve or 0) + (agg['approuve'] or 0)
    paye = (demande.montant_paye or 0) + (agg['paye'] or 0)
    return {'engage_total': str(engage), 'paye_total': str(paye), 'solde_total': str(engage - paye),
            'complements': [{'id': c.pk, 'reference': c.reference, 'objet': c.objet, 'statut': c.statut,
                             'statut_libelle': c.get_statut_display(), 'montant_demande': c.montant_demande,
                             'montant_approuve': c.montant_approuve, 'montant_paye': c.montant_paye}
                            for c in complements.exclude(statut=StatutDemande.BROUILLON).order_by('created_at')]}


def peut_corriger_montant(demande, user):
    """Décision 11 : le DAF (titulaire) ou un administrateur des finances, tant que rien n'est payé."""
    from api import organisation as org
    if demande.statut not in STATUTS_PAYABLES or (demande.montant_paye or 0) > 0 or not demande.type_demande.avec_montant:
        return False
    return is_admin_finances(user) or any(u.pk == user.pk for u in org.titulaires('DAF'))


def corriger_montant_approuve(demande, user, montant, motif, infos=None):
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier({'motif': 'Le motif de la correction est obligatoire.'})
    montant = _montant(montant)
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        if not peut_corriger_montant(demande, user):
            raise Interdit("Correction impossible : réservée au DAF, avant tout paiement d'une demande approuvée.")
        if annulation_en_cours(demande) is not None:
            raise ErreurMetier("Une demande d'annulation est en cours.")
        ancien = demande.montant_approuve
        if montant == ancien:
            raise ErreurMetier({'montant': 'Le montant est inchangé.'})
        demande.montant_approuve = montant
        demande.save(update_fields=['montant_approuve', 'updated_at'])
        moteur.tracer(demande, 'correction', auteur=user, infos=infos,
                      motif=f"Montant approuvé corrigé : {fmt(ancien, demande.devise)} → {fmt(montant, demande.devise)}. {motif}",
                      donnees={'avant': {'montant_approuve': str(ancien)}, 'apres': {'montant_approuve': str(montant)}})
        mettre_a_jour(demande, user, infos)
        notifier([demande.demandeur] + comptables(), 'correction', f"{demande.reference} : montant approuvé corrigé",
                 f"Nouveau montant approuvé : {fmt(montant, demande.devise)} ({motif}).", demande)
    return demande
