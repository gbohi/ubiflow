"""
Moteur de workflow (§5.4 à §5.9) : calcul du plan de validation, ouverture
des étapes, tâches, actions des valideurs, délégations, réaffectation.

Toutes les fonctions d'écriture doivent être appelées dans une transaction
(les services des demandes s'en chargent).
"""
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from api import organisation as org
from notifications.services import administrateurs, notifier

from . import conditions
from .erreurs import ErreurMetier, Interdit
from .models import Action, Delegation, EtapeInstance, InstanceWorkflow, Tache, VersionWorkflow


def nom(u):
    return (f"{u.nom} {u.prenom}".strip() or u.username) if u else '—'


def _personne(u, responsabilite_id=None, **extra):
    return {'id': u.pk, 'nom': nom(u), 'matricule': u.username, 'responsabilite': responsabilite_id, **extra}


def version_publiee(type_demande):
    return VersionWorkflow.objects.filter(type_demande=type_demande, etat='publiee').first()


# ═══════════════════════════════════════════════════════════════
# RÉSOLUTION DES VALIDEURS ET PLAN
# ═══════════════════════════════════════════════════════════════

def resoudre_regle(regle, demande, d):
    """Liste de (user, responsabilite_id) désignés par une règle, à la date d."""
    if regle.mode == 'personne':
        return [(regle.personne, None)] if regle.personne and regle.personne.is_active else []
    if regle.mode == 'responsabilite':
        dept = demande.departement if regle.perimetre == 'departement_demandeur' else None
        agence = demande.agence if regle.perimetre == 'agence_demandeur' else None
        return [(u, regle.responsabilite_id)
                for u in org.titulaires(regle.responsabilite, d, departement=dept, agence=agence)]
    # Relations hiérarchiques : à partir des données figées de la demande
    n1 = demande.n_plus_1
    if regle.relation == 'n_plus_1':
        cible = n1
    elif regle.relation == 'n_plus_2':
        cible = org.n_plus_1(n1, d).responsable if n1 else None
    elif regle.relation == 'responsable_departement':
        cible = org.responsable_departement(demande.departement, d) if demande.departement_id else None
    else:  # responsable_departement_parent
        parent = demande.departement.parent if demande.departement_id else None
        cible = org.responsable_departement(parent, d) if parent else None
    return [(cible, None)] if cible is not None and cible.is_active else []


def resoudre_etape(etape, demande, d):
    """Valideurs de l'étape (union des règles, sans doublon, dans l'ordre des règles)."""
    vus, resultat = set(), []
    for regle in etape.regles.select_related('responsabilite', 'personne'):
        for user, resp in resoudre_regle(regle, demande, d):
            if user.pk not in vus:
                vus.add(user.pk)
                resultat.append((user, resp))
    return resultat


def entree_plan(etape, demande, d, contexte, libelles):
    """Entrée du plan pour une étape : prévue (valideurs), sautée ou bloquante (raison)."""
    base = {'etape': etape.pk, 'ordre': etape.ordre, 'code': etape.code, 'libelle': etape.libelle,
            'mode': etape.mode, 'regle_parallele': etape.regle_parallele, 'quorum': etape.quorum,
            'valideurs': [], 'raison': ''}
    if etape.condition and not conditions.evaluer(etape.condition, contexte):
        return {**base, 'statut': 'sautee',
                'raison': f"Condition non remplie : {conditions.decrire(etape.condition, libelles)}"}

    valideurs = resoudre_etape(etape, demande, d)
    if not valideurs:
        if etape.valideur_introuvable == 'sauter':
            return {**base, 'statut': 'sautee', 'raison': 'Aucun valideur trouvé : étape sautée.'}
        if etape.valideur_introuvable == 'secours' and etape.valideur_secours and etape.valideur_secours.is_active:
            valideurs = [(etape.valideur_secours, None)]
            base['raison'] = 'Aucun valideur trouvé : valideur de secours.'
        else:
            return {**base, 'statut': 'bloquante',
                    'raison': f"Aucun valideur trouvé pour l'étape « {etape.libelle} »."}

    demandeur = demande.demandeur
    if any(u.pk == demandeur.pk for u, _ in valideurs):
        regle = etape.auto_validation_demandeur
        if regle == 'sauter':
            valideurs = [(u, r) for u, r in valideurs if u.pk != demandeur.pk]
            if not valideurs:
                return {**base, 'statut': 'sautee', 'raison': "Le demandeur est le valideur : étape sautée."}
        elif regle == 'remonter':
            n1 = demande.n_plus_1
            if n1 is None or not n1.is_active or n1.pk == demandeur.pk:
                return {**base, 'statut': 'bloquante',
                        'raison': f"Étape « {etape.libelle} » : le demandeur en est le valideur et son N+1 est introuvable."}
            valideurs = [(n1, None) if u.pk == demandeur.pk else (u, r) for u, r in valideurs]
            valideurs = list({u.pk: (u, r) for u, r in valideurs}.values())
            base['raison'] = 'Le demandeur est le valideur : étape confiée à son N+1.'

    return {**base, 'statut': 'prevue', 'valideurs': [
        _personne(u, r, auto_validation=(u.pk == demandeur.pk),
                  approbation_automatique=(u.pk == demandeur.pk and etape.auto_validation_demandeur == 'automatique'))
        for u, r in valideurs]}


def calculer_plan(version, demande, d, contexte):
    """Plan de validation complet pour une demande (sans rien enregistrer)."""
    libelles = {c['code']: c['libelle'] for c in conditions.champs_disponibles(version.type_demande)}
    etapes = (version.etapes.filter(active=True)
              .select_related('valideur_secours').prefetch_related('regles'))
    return [entree_plan(e, demande, d, contexte, libelles) for e in etapes]


def blocages(plan):
    return [e['raison'] for e in plan if e['statut'] == 'bloquante']


# ═══════════════════════════════════════════════════════════════
# EXÉCUTION
# ═══════════════════════════════════════════════════════════════

def tracer(demande, type_action, *, auteur=None, instance=None, etape_instance=None, tache=None, motif='',
           donnees=None, pour_compte_de=None, delegation=None, auto_validation=False, infos=None):
    infos = infos or {}
    return Action.objects.create(
        demande=demande, type=type_action, auteur_reel=auteur, instance=instance, etape_instance=etape_instance,
        tache=tache, motif=motif or '', donnees=donnees, pour_compte_de=pour_compte_de, delegation=delegation,
        auto_validation=auto_validation, canal=infos.get('canal', ''), adresse_ip=infos.get('adresse_ip'))


def demarrer(demande, version, plan, cycle, d, reprise=None, infos=None):
    """
    Crée l'instance du cycle et ouvre la première étape à traiter.
    reprise = {etape_id: instance précédente} pour les étapes reprises d'un cycle antérieur.
    """
    instance = InstanceWorkflow.objects.create(demande=demande, version=version, cycle=cycle, date_reference=d,
                                               plan=plan)
    reprise = reprise or set()
    for entree in plan:
        ei = EtapeInstance.objects.create(instance=instance, etape_id=entree['etape'], ordre=entree['ordre'])
        if entree['statut'] == 'sautee':
            ei.etat, ei.motif_saut, ei.cloturee_le = 'sautee', entree['raison'], timezone.now()
            ei.save()
            tracer(demande, 'saut', instance=instance, etape_instance=ei, motif=entree['raison'], infos=infos)
        elif entree['etape'] in reprise:
            ei.etat, ei.reprise, ei.cloturee_le = 'approuvee', True, timezone.now()
            ei.save()
    ouvrir_suivante(instance, infos)
    return instance


def ouvrir_suivante(instance, infos=None):
    ei = instance.etapes.filter(etat='a_venir').order_by('ordre').first()
    if ei is None:
        finaliser(instance, infos)
    else:
        ouvrir_etape(ei, infos)


def _entree(instance, etape_id):
    return next((e for e in instance.plan if e['etape'] == etape_id), None)


def ouvrir_etape(ei, infos=None):
    """
    Ouvre l'étape : valideurs vérifiés (titulaires en cours ; N+1 figé), tâches
    créées, approbations automatiques appliquées, valideurs notifiés.
    """
    instance, demande, etape = ei.instance, ei.instance.demande, ei.etape
    prevus = [v['id'] for v in (_entree(instance, etape.pk) or {}).get('valideurs', [])]
    libelles = {c['code']: c['libelle'] for c in conditions.champs_disponibles(demande.type_demande)}
    from demandes.services import contexte_conditions
    actuelle = entree_plan(etape, demande, timezone.localdate(), contexte_conditions(demande), libelles)
    valideurs = actuelle['valideurs'] if actuelle['statut'] == 'prevue' else []
    if not valideurs:
        # Plus personne à cette étape aujourd'hui : on garde les valideurs prévus et on alerte
        from django.contrib.auth import get_user_model
        users = {u.pk: u for u in get_user_model().objects.filter(pk__in=prevus)}
        valideurs = [_personne(users[i], None, auto_validation=(i == demande.demandeur_id),
                               approbation_automatique=False) for i in prevus if i in users]
        notifier(administrateurs(), 'workflow_a_reaffecter', f"{demande.reference} : valideur à réaffecter",
                 f"Étape « {etape.libelle} » : {actuelle['raison'] or 'aucun valideur disponible'}.", demande)
    elif [v['id'] for v in valideurs] != prevus:
        tracer(demande, 'reresolution', instance=instance, etape_instance=ei, infos=infos,
               motif="Valideurs mis à jour à l'ouverture de l'étape (titulaires en cours).",
               donnees={'prevus': prevus, 'retenus': [v['id'] for v in valideurs]})

    ei.etat, ei.ouverte_le = 'en_cours', timezone.now()
    ei.save()
    parallele = etape.mode == 'parallele'
    for i, v in enumerate(valideurs, start=1):
        Tache.objects.create(etape_instance=ei, valideur_id=v['id'], ordre=i, responsabilite_id=v.get('responsabilite'),
                             auto_validation=v.get('auto_validation', False),
                             etat='en_attente' if (parallele or i == 1) else 'a_venir',
                             ouverte_le=timezone.now() if (parallele or i == 1) else None)
    _traiter_ouvertures(ei, infos)


def _deja_approuve(ei, user_id):
    return Tache.objects.filter(etape_instance__instance=ei.instance, etape_instance__ordre__lt=ei.ordre,
                                valideur_id=user_id, decision='approuvee').exists()


def _traiter_ouvertures(ei, infos):
    """Approbations automatiques des tâches qui viennent de s'ouvrir, puis notifications."""
    etape, demande = ei.etape, ei.instance.demande
    while True:
        auto = None
        for t in ei.taches.filter(etat='en_attente').select_related('valideur'):
            if t.valideur_id == demande.demandeur_id and etape.auto_validation_demandeur == 'automatique':
                auto = (t, "Le demandeur est le valideur de cette étape : approbation automatique.")
            elif (etape.meme_valideur_deja_passe == 'approbation_automatique' and _deja_approuve(ei, t.valideur_id)):
                auto = (t, "Déjà approuvée par ce valideur à une étape précédente : approbation automatique.")
            if auto:
                break
        if not auto:
            break
        tache, motif = auto
        tache.etat, tache.decision, tache.traitee_le = 'faite', 'approuvee', timezone.now()
        tache.save()
        tracer(demande, 'auto_approbation', instance=ei.instance, etape_instance=ei, tache=tache, motif=motif,
               auto_validation=tache.auto_validation, infos=infos, pour_compte_de=tache.valideur)
        if _apres_approbation(tache, infos):
            return  # étape terminée (l'étape suivante a été ouverte)
    en_attente = list(ei.taches.filter(etat='en_attente').select_related('valideur'))
    destinataires = [t.valideur for t in en_attente]
    destinataires += [d.delegataire for t in en_attente for d in delegations_couvrant(t)]
    if destinataires:
        notifier(destinataires, 'validation_attendue', f"Validation attendue : {demande.reference}",
                 f"{demande.type_demande.libelle} de {nom(demande.demandeur)} — étape « {etape.libelle} ».", demande)


def _regle_atteinte(ei):
    etape = ei.etape
    taches = [t for t in ei.taches.all() if t.etat != 'annulee']
    approuvees = sum(1 for t in taches if t.decision == 'approuvee')
    if etape.mode == 'sequentiel' or etape.regle_parallele == 'tous':
        return approuvees >= len(taches)
    if etape.regle_parallele == 'un_seul':
        return approuvees >= 1
    return approuvees >= min(etape.quorum or len(taches), len(taches))


def _apres_approbation(tache, infos):
    """Après une approbation : tâche suivante ou étape terminée. Renvoie True si l'étape est close."""
    ei = tache.etape_instance
    if _regle_atteinte(ei):
        ei.taches.filter(etat__in=['en_attente', 'a_venir']).update(etat='annulee')
        ei.etat, ei.cloturee_le = 'approuvee', timezone.now()
        ei.save()
        demande = ei.instance.demande
        notifier([demande.demandeur], 'validation_effectuee', f"{demande.reference} : étape validée",
                 f"L'étape « {ei.etape.libelle} » a été validée.", demande)
        ouvrir_suivante(ei.instance, infos)
        return True
    if ei.etape.mode == 'sequentiel':
        suivante = ei.taches.filter(etat='a_venir').order_by('ordre').first()
        if suivante:
            suivante.etat, suivante.ouverte_le = 'en_attente', timezone.now()
            suivante.save()
            _traiter_ouvertures(ei, infos)
    return False


def finaliser(instance, infos=None):
    from demandes.models import StatutDemande, StatutFinancier
    demande = instance.demande
    instance.etat, instance.terminee_le = 'approuvee', timezone.now()
    instance.save()
    if demande.montant_approuve is None:
        demande.montant_approuve = demande.montant_demande
    demande.statut, demande.approuvee_le = StatutDemande.APPROUVEE, timezone.now()
    demande.save()
    tracer(demande, 'approbation_finale', instance=instance, infos=infos,
           motif='Toutes les étapes du circuit sont validées.')
    notifier([demande.demandeur], 'demande_approuvee', f"{demande.reference} approuvée",
             f"Votre demande « {demande.objet} » est approuvée.", demande)
    from demandes import extensions
    from tresorerie.services import comptables, fmt, mettre_a_jour
    extensions.pour(demande.type_demande).apres_approbation(demande, infos)
    mettre_a_jour(demande, infos=infos)  # à payer, ou clôture immédiate d'une demande sans montant (mode A)
    if demande.statut_financier == StatutFinancier.A_PAYER:
        notifier(comptables(), 'a_payer', f"{demande.reference} à payer",
                 f"{demande.type_demande.libelle} de {nom(demande.demandeur)} : "
                 f"{fmt(demande.montant_approuve, demande.devise)}.", demande)


# ═══════════════════════════════════════════════════════════════
# DÉLÉGATIONS ET TÂCHES VISIBLES
# ═══════════════════════════════════════════════════════════════

def delegations_actives(d=None):
    d = d or timezone.localdate()
    return Delegation.objects.filter(revoquee=False, date_debut__lte=d, date_fin__gte=d)


def couvre(delegation, tache):
    """La délégation couvre-t-elle cette tâche (délégant, types, responsabilités, demandeur) ?"""
    demande = tache.etape_instance.instance.demande
    if delegation.delegant_id != tache.valideur_id or delegation.delegataire_id == demande.demandeur_id:
        return False
    types = {t.pk for t in delegation.types_demande.all()}
    if types and demande.type_demande_id not in types:
        return False
    resps = {r.pk for r in delegation.responsabilites.all()}
    return not resps or tache.responsabilite_id in resps


def delegations_couvrant(tache):
    return [d for d in delegations_actives().filter(delegant_id=tache.valideur_id).prefetch_related(
        'types_demande', 'responsabilites') if couvre(d, tache)]


def filtre_taches_de(user):
    """Q des tâches traitables par user : les siennes et celles reçues par délégation active."""
    q = Q(valideur=user)
    for d in delegations_actives().filter(delegataire=user).prefetch_related('types_demande', 'responsabilites'):
        sous = Q(valideur_id=d.delegant_id) & ~Q(etape_instance__instance__demande__demandeur=user)
        types = [t.pk for t in d.types_demande.all()]
        if types:
            sous &= Q(etape_instance__instance__demande__type_demande__in=types)
        resps = [r.pk for r in d.responsabilites.all()]
        if resps:
            sous &= Q(responsabilite__in=resps)
        q |= sous
    return q


# ═══════════════════════════════════════════════════════════════
# ACTIONS DES VALIDEURS
# ═══════════════════════════════════════════════════════════════

def habilitation(tache, user):
    """(pour_compte_de, délégation) si user peut traiter la tâche, sinon Interdit."""
    if tache.valideur_id == user.pk:
        return None, None
    for d in delegations_couvrant(tache):
        if d.delegataire_id == user.pk:
            return tache.valideur, d
    raise Interdit("Cette validation ne vous est pas attribuée.")


def _appliquer_modifications(tache, user, modifications, infos):
    """Corrections autorisées par l'étape (champs du type, montant approuvé)."""
    from demandes.models import VersionContenu
    from demandes.services import valider_contenu
    ei = tache.etape_instance
    demande, etape = ei.instance.demande, ei.etape
    autorises = set(etape.champs_modifiables or [])
    interdits = set(modifications) - autorises
    if interdits:
        raise ErreurMetier(f"Champ(s) non modifiable(s) à cette étape : {', '.join(sorted(interdits))}.")
    avant, apres = {}, {}
    if 'montant_approuve' in modifications:
        try:
            montant = Decimal(str(modifications.pop('montant_approuve')))
        except (InvalidOperation, ValueError):
            raise ErreurMetier("Montant approuvé invalide.")
        if montant < 0:
            raise ErreurMetier("Le montant approuvé ne peut pas être négatif.")
        avant['montant_approuve'] = str(demande.montant_approuve or demande.montant_demande)
        apres['montant_approuve'] = str(montant)
        demande.montant_approuve = montant
        demande.save(update_fields=['montant_approuve', 'updated_at'])
    if modifications:
        donnees = {**demande.donnees, **modifications}
        donnees = valider_contenu(demande.type_demande, donnees, complet=True)
        for code in modifications:
            avant[code], apres[code] = demande.donnees.get(code), donnees.get(code)
        demande.donnees = donnees
        precedente = demande.version_courante
        version = VersionContenu.objects.create(
            demande=demande, numero=(precedente.numero + 1) if precedente else 1, origine='correction_valideur',
            objet=demande.objet, montant_demande=demande.montant_demande, devise=demande.devise, donnees=donnees,
            motif_modification=f"Correction à l'étape « {etape.libelle} »", cree_par=user)
        demande.version_courante = version
        demande.save(update_fields=['donnees', 'version_courante', 'updated_at'])
    if avant:
        tracer(demande, 'correction', auteur=user, instance=ei.instance, etape_instance=ei, tache=tache,
               donnees={'avant': avant, 'apres': apres}, infos=infos)


def agir(tache, user, action, motif='', modifications=None, infos=None):
    """approuver | rejeter | retourner une tâche en attente."""
    from demandes.models import StatutDemande
    from demandes.services import verifier_pieces_etape
    tache = Tache.objects.select_for_update().select_related(
        'etape_instance__etape', 'etape_instance__instance__demande__type_demande').get(pk=tache.pk)
    ei = tache.etape_instance
    instance, demande, etape = ei.instance, ei.instance.demande, ei.etape
    if tache.etat != 'en_attente' or ei.etat != 'en_cours' or instance.etat != 'en_cours' \
            or demande.statut != StatutDemande.EN_VALIDATION:
        raise ErreurMetier("Cette validation n'est plus en attente.")
    pour_compte_de, delegation = habilitation(tache, user)
    if action != 'approuver' and action not in (etape.actions_autorisees or []):
        raise ErreurMetier(f"L'action « {action} » n'est pas autorisée à l'étape « {etape.libelle} ».")
    motif = (motif or '').strip()
    if action in ('rejeter', 'retourner') and not motif:
        raise ErreurMetier("Le motif est obligatoire.")

    commun = dict(auteur=user, instance=instance, etape_instance=ei, tache=tache, motif=motif,
                  pour_compte_de=pour_compte_de, delegation=delegation, infos=infos,
                  auto_validation=(user.pk == demande.demandeur_id))
    if action == 'approuver':
        if modifications:
            _appliquer_modifications(tache, user, dict(modifications), infos)
        verifier_pieces_etape(demande, etape)
        tache.etat, tache.decision, tache.traitee_par, tache.traitee_le = 'faite', 'approuvee', user, timezone.now()
        tache.save()
        tracer(demande, 'approbation', **commun)
        _apres_approbation(tache, infos)
        return

    decision = 'rejetee' if action == 'rejeter' else 'retournee'
    tache.etat, tache.decision, tache.traitee_par, tache.traitee_le = 'faite', decision, user, timezone.now()
    tache.save()
    Tache.objects.filter(etape_instance__instance=instance, etat__in=['en_attente', 'a_venir']).update(etat='annulee')
    ei.etat, ei.cloturee_le = decision, timezone.now()
    ei.save()
    instance.etapes.filter(etat='a_venir').update(etat='annulee')
    instance.etat, instance.terminee_le = decision, timezone.now()
    if action == 'retourner':
        instance.etape_retour = etape
    instance.save()
    if action == 'rejeter':
        demande.statut = StatutDemande.REJETEE
        demande.save(update_fields=['statut', 'updated_at'])
        tracer(demande, 'rejet', **commun)
        notifier([demande.demandeur], 'demande_rejetee', f"{demande.reference} rejetée",
                 f"Motif : {motif}", demande)
    else:
        demande.statut = StatutDemande.A_CORRIGER
        demande.save(update_fields=['statut', 'updated_at'])
        tracer(demande, 'retour', **commun)
        notifier([demande.demandeur], 'demande_retournee', f"{demande.reference} à corriger",
                 f"Motif : {motif}", demande)


def annuler_instance(instance, auteur, motif, infos=None):
    """Annule le cycle en cours (annulation de la demande) et prévient les valideurs en attente."""
    en_attente = list(Tache.objects.filter(etape_instance__instance=instance, etat='en_attente')
                      .select_related('valideur'))
    Tache.objects.filter(etape_instance__instance=instance, etat__in=['en_attente', 'a_venir']).update(etat='annulee')
    instance.etapes.filter(etat__in=['a_venir', 'en_cours']).update(etat='annulee')
    instance.etat, instance.terminee_le = 'annulee', timezone.now()
    instance.save()
    demande = instance.demande
    notifier([t.valideur for t in en_attente], 'demande_annulee', f"{demande.reference} annulée",
             f"Le demandeur a annulé sa demande. Motif : {motif}", demande)


def reaffecter_tache(tache, nouveau, auteur, motif, infos=None):
    """Réaffectation exceptionnelle d'une tâche à un autre valideur (§5.9)."""
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier("Le motif est obligatoire.")
    if tache.etat not in ('en_attente', 'a_venir'):
        raise ErreurMetier("Seule une validation en attente peut être réaffectée.")
    if not nouveau.is_active:
        raise ErreurMetier("Le nouveau valideur n'est pas actif.")
    demande = tache.etape_instance.instance.demande
    if nouveau.pk == tache.valideur_id:
        raise ErreurMetier("C'est déjà le valideur de cette tâche.")
    ancien = tache.valideur
    tache.valideur, tache.auto_validation = nouveau, nouveau.pk == demande.demandeur_id
    tache.save()
    tracer(demande, 'reaffectation', auteur=auteur, instance=tache.etape_instance.instance,
           etape_instance=tache.etape_instance, tache=tache, motif=motif, infos=infos,
           donnees={'ancien': _personne(ancien), 'nouveau': _personne(nouveau)})
    if tache.etat == 'en_attente':
        notifier([nouveau], 'validation_attendue', f"Validation attendue : {demande.reference}",
                 f"Validation qui vous a été réaffectée — étape « {tache.etape_instance.etape.libelle} ».", demande)
