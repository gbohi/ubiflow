"""
Clôture des missions (§9, mode B) :
1. la mission approuvée passe « En attente de clôture » ;
2. le demandeur déclare dates réelles, dépenses réelles (rubriques de la note de
   frais), observations, et joint le rapport et les pièces exigées « à la clôture » ;
3. contrôle facultatif (paramètre du type `controle_cloture` : rôle qui valide ou
   retourne avec motif) ;
4. à la validation : dépenses retenues, reversement si le payé les dépasse ;
5. la mission est clôturée dès qu'elle est payée et qu'aucun reversement n'est attendu.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from api.permissions import get_roles, is_admin
from demandes.models import Demande, StatutDemande
from notifications.services import notifier
from workflow import moteur
from workflow.erreurs import ErreurMetier, Interdit

from .models import ClotureMission

RUBRIQUES = ClotureMission.RUBRIQUES
LIBELLES = {'hotel': "Frais d'hôtel (petit déjeuner compris)", 'transport': 'Transport (location de véhicule)',
            'indemnites': 'Indemnités journalières', 'telephone': 'Frais de téléphone', 'divers': 'Divers',
            'reception': 'Réception', 'detaxe': 'Détaxe (à reverser)', 'a_refacturer': 'Autres frais à refacturer'}


def _d(v):
    try:
        x = Decimal(str(v or 0).replace(' ', '').replace(',', '.')).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise ErreurMetier('Montant invalide.')
    if x < 0:
        raise ErreurMetier('Les montants ne peuvent pas être négatifs.')
    return x


def role_controle(demande):
    return (demande.type_demande.parametres or {}).get('controle_cloture') or None


def peut_controler(demande, user):
    role = role_controle(demande)
    return bool(role) and demande.demandeur_id != user.pk and (is_admin(user) or role in get_roles(user))


def obtenir(demande):
    cloture, _ = ClotureMission.objects.get_or_create(demande=demande)
    return cloture


def calculer(demande, cloture):
    """Note de frais réelle : indemnités (jours réels × tarif figé), total, avance, solde, reversement."""
    from tresorerie.services import synthese
    fig = (demande.parametres_figes or {}).get('missions') or {}
    jours = tarif = None
    indemnites = Decimal('0')
    pd = fig.get('per_diem')
    if cloture.depart_reel and cloture.retour_reel and pd:
        jours = (cloture.retour_reel - cloture.depart_reel).days + 1
        t = (fig.get('taux') or {}).get(pd['devise'])
        tarif = Decimal(pd['montant'])
        indemnites = (tarif * jours * Decimal(t['taux'] if t else '1')).quantize(Decimal('0.01'))
    dep = {r: _d((cloture.depenses or {}).get(r)) for r in RUBRIQUES}
    charges = dep['hotel'] + dep['transport'] + indemnites + dep['telephone'] + dep['divers'] + dep['reception'] - dep['detaxe']
    total = charges + dep['a_refacturer']
    s = synthese(demande)
    complements_approuves = Decimal(s['engage_total']) - (demande.montant_approuve or 0)
    paye_total = Decimal(s['paye_total'])
    retenu_mission = max(Decimal('0'), min(total - complements_approuves, demande.montant_approuve or Decimal('0')))
    depassement = max(Decimal('0'), total - Decimal(s['engage_total']))
    return {
        'jours': jours, 'tarif_jour': str(tarif) if tarif is not None else None, 'devise_tarif': pd['devise'] if pd else '',
        'indemnites': str(indemnites), **{r: str(v) for r, v in dep.items()},
        'divers_detail': (cloture.depenses or {}).get('divers_detail', ''),
        'a_refacturer_detail': (cloture.depenses or {}).get('a_refacturer_detail', ''),
        'total_charges': str(charges), 'total': str(total), 'engage_total': s['engage_total'], 'avance': str(paye_total),
        'a_rembourser': str(max(paye_total - total, Decimal('0'))), 'a_reverser': str(max(total - paye_total, Decimal('0'))),
        'retenu_mission': str(retenu_mission), 'depassement': str(depassement),
        'devise': demande.devise_reference or demande.devise,
    }


def serialiser(demande, cloture, user):
    return {'etat': cloture.etat, 'etat_libelle': cloture.get_etat_display(), 'depart_reel': cloture.depart_reel,
            'retour_reel': cloture.retour_reel, 'depenses': cloture.depenses, 'observations': cloture.observations,
            'soumise_le': cloture.soumise_le, 'controlee_le': cloture.controlee_le,
            'controlee_par': moteur.nom(cloture.controlee_par) if cloture.controlee_par_id else None,
            'motif_retour': cloture.motif_retour, 'controle': role_controle(demande),
            'calcul': cloture.calcul if cloture.etat == 'validee' else calculer(demande, cloture),
            'pieces_cloture': [{'id': e.type_piece_id, 'libelle': e.type_piece.libelle, 'obligatoire': e.obligatoire,
                                'fournie': demande.documents.filter(retire=False, type_piece=e.type_piece_id).exists()}
                               for e in demande.type_demande.exigences.filter(moment='cloture').select_related('type_piece')],
            'actions': {'modifier': demande.demandeur_id == user.pk and demande.statut == StatutDemande.EN_ATTENTE_CLOTURE
                        and cloture.etat in ('brouillon', 'retournee'),
                        'controler': cloture.etat == 'soumise' and peut_controler(demande, user)}}


def _exiger_saisie(demande, user, cloture):
    if demande.demandeur_id != user.pk:
        raise Interdit("Seul le demandeur déclare la clôture de sa mission.")
    if demande.statut != StatutDemande.EN_ATTENTE_CLOTURE:
        raise ErreurMetier("La mission n'est pas en attente de clôture.")
    if cloture.etat not in ('brouillon', 'retournee'):
        raise ErreurMetier("Les éléments de clôture sont déjà soumis.")


def enregistrer(demande, user, donnees):
    from datetime import date
    cloture = obtenir(demande)
    _exiger_saisie(demande, user, cloture)
    for cle in ('depart_reel', 'retour_reel'):
        if cle in donnees:
            v = donnees.get(cle)
            try:
                setattr(cloture, cle, date.fromisoformat(str(v)[:10]) if v else None)
            except ValueError:
                raise ErreurMetier({cle: 'Date invalide.'})
    if cloture.depart_reel and cloture.retour_reel and cloture.retour_reel < cloture.depart_reel:
        raise ErreurMetier({'retour_reel': 'Le retour ne peut pas précéder le départ.'})
    if 'depenses' in donnees:
        dep = donnees.get('depenses') or {}
        propre = {r: str(_d(dep.get(r))) for r in RUBRIQUES}
        propre['divers_detail'] = str(dep.get('divers_detail') or '')[:500]
        propre['a_refacturer_detail'] = str(dep.get('a_refacturer_detail') or '')[:500]
        cloture.depenses = propre
    if 'observations' in donnees:
        cloture.observations = str(donnees.get('observations') or '')[:5000]
    cloture.save()
    return cloture


def soumettre(demande, user, infos=None):
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        cloture = obtenir(demande)
        _exiger_saisie(demande, user, cloture)
        erreurs = {}
        if not cloture.depart_reel:
            erreurs['depart_reel'] = 'La date de départ réelle est obligatoire.'
        if not cloture.retour_reel:
            erreurs['retour_reel'] = 'La date de retour réelle est obligatoire.'
        fournies = set(demande.documents.filter(retire=False).values_list('type_piece_id', flat=True))
        manquantes = [e.type_piece.libelle for e in demande.type_demande.exigences.filter(
            moment='cloture', obligatoire=True).select_related('type_piece') if e.type_piece_id not in fournies]
        if manquantes:
            erreurs['documents'] = f"Pièce(s) obligatoire(s) à joindre : {', '.join(manquantes)}."
        if erreurs:
            raise ErreurMetier(erreurs)
        cloture.etat, cloture.soumise_le, cloture.motif_retour = 'soumise', timezone.now(), ''
        cloture.save()
        moteur.tracer(demande, 'cloture', auteur=user, infos=infos, motif='Éléments de clôture soumis.')
        role = role_controle(demande)
        if role:
            from django.contrib.auth import get_user_model
            controleurs = get_user_model().objects.filter(is_active=True, groups__name=role).exclude(pk=demande.demandeur_id)
            notifier(list(controleurs.distinct()), 'cloture_a_controler', f"{demande.reference} : clôture à contrôler",
                     f"{moteur.nom(demande.demandeur)} a soumis la clôture de sa mission.", demande)
        else:
            _valider(demande, cloture, None, infos)
    return cloture


def valider(demande, user, infos=None):
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        cloture = obtenir(demande)
        if cloture.etat != 'soumise':
            raise ErreurMetier("Aucune clôture à contrôler.")
        if not peut_controler(demande, user):
            raise Interdit("Vous ne pouvez pas contrôler cette clôture.")
        _valider(demande, cloture, user, infos)
    return cloture


def _valider(demande, cloture, user, infos):
    """Dépenses retenues, reversement éventuel, note de frais réelle, clôture si tout est soldé."""
    from tresorerie.services import creer_reversement, fmt, mettre_a_jour
    calcul = calculer(demande, cloture)
    cloture.calcul, cloture.etat = calcul, 'validee'
    cloture.controlee_par, cloture.controlee_le = user, timezone.now()
    cloture.save()
    demande.montant_retenu = Decimal(calcul['retenu_mission'])
    demande.parametres_figes = {**(demande.parametres_figes or {}), 'cloture': {'note_frais': calcul}}
    demande.save(update_fields=['montant_retenu', 'parametres_figes', 'updated_at'])
    devise = demande.devise
    moteur.tracer(demande, 'cloture', auteur=user, infos=infos,
                  motif=f"Clôture validée{' par ' + moteur.nom(user) if user else ''} : dépenses réelles "
                        f"{fmt(Decimal(calcul['total']), calcul['devise'])}, montant retenu {fmt(demande.montant_retenu, devise)}.")
    trop_percu = (demande.montant_paye or 0) - demande.montant_retenu - (demande.montant_reverse or 0)
    if trop_percu > 0:
        creer_reversement(demande, trop_percu, 'cloture',
                          f"Dépenses réelles inférieures au montant payé ({fmt(Decimal(calcul['total']), calcul['devise'])})",
                          user, infos)
    if Decimal(calcul['depassement']) > 0:
        notifier([demande.demandeur], 'cloture', f"{demande.reference} : dépenses supérieures à l'engagé",
                 f"Vos dépenses dépassent l'engagé de {fmt(Decimal(calcul['depassement']), calcul['devise'])} : "
                 "faites une demande de frais complémentaires pour ce montant.", demande)
    mettre_a_jour(demande, user, infos)
    notifier([demande.demandeur], 'cloture', f"{demande.reference} : clôture validée",
             "Vos éléments de clôture sont validés." + (" Un reversement est attendu." if trop_percu > 0 else ''), demande)


def retourner(demande, user, motif, infos=None):
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier({'motif': 'Le motif du retour est obligatoire.'})
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        cloture = obtenir(demande)
        if cloture.etat != 'soumise':
            raise ErreurMetier("Aucune clôture à contrôler.")
        if not peut_controler(demande, user):
            raise Interdit("Vous ne pouvez pas contrôler cette clôture.")
        cloture.etat, cloture.motif_retour = 'retournee', motif
        cloture.controlee_par, cloture.controlee_le = user, timezone.now()
        cloture.save()
        moteur.tracer(demande, 'cloture', auteur=user, infos=infos, motif=f"Éléments de clôture retournés : {motif}")
        notifier([demande.demandeur], 'cloture', f"{demande.reference} : clôture à compléter",
                 f"{moteur.nom(user)} vous retourne les éléments de clôture : {motif}", demande)
    return cloture
