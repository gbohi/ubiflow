"""
Services des demandes : la seule porte d'entrée pour modifier une demande
(l'API web et mobile les appelle, aucune règle dans les vues).
"""
import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from api import organisation as org
from api.models import ParametreSysteme
from api.permissions import voit_toutes_les_demandes
from notifications.services import administrateurs, notifier
from workflow import moteur
from workflow.erreurs import ErreurMetier, Interdit
from workflow.models import Tache

from . import extensions
from .models import (
    CompteurReference, Demande, Document, StatutDemande, StatutFinancier, VersionContenu,
)

EXTENSIONS_AUTORISEES = {'pdf', 'jpg', 'jpeg', 'png', 'webp', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods'}


# ═══════════════════════════════════════════════════════════════
# CONTENU : VALIDATION DES CHAMPS
# ═══════════════════════════════════════════════════════════════

def _valeur(champ, brute):
    """Valeur normalisée d'un champ selon sa nature (lève ValueError si invalide)."""
    n = champ.nature
    if n in ('texte', 'texte_long'):
        texte = str(brute).strip()
        if len(texte) > (5000 if n == 'texte_long' else 500):
            raise ValueError('texte trop long')
        return texte
    if n == 'entier':
        if isinstance(brute, bool) or str(brute).strip().lstrip('-') == '':
            raise ValueError
        valeur = int(str(brute).strip())
        if valeur < 0:
            raise ValueError('nombre négatif')
        return valeur
    if n == 'montant':
        valeur = Decimal(str(brute).replace(' ', '').replace(',', '.'))
        if valeur < 0:
            raise ValueError('montant négatif')
        return str(valeur.quantize(Decimal('0.01')))
    if n == 'date':
        return date.fromisoformat(str(brute)[:10]).isoformat()
    if n == 'datetime':
        return datetime.fromisoformat(str(brute).replace('Z', '+00:00')).isoformat()
    if n == 'liste':
        if str(brute) not in [str(o) for o in champ.options]:
            raise ValueError('valeur hors liste')
        return str(brute)
    if n == 'booleen':
        if isinstance(brute, bool):
            return brute
        if str(brute).lower() in ('true', '1', 'oui'):
            return True
        if str(brute).lower() in ('false', '0', 'non'):
            return False
        raise ValueError
    if n == 'collaborateur':
        user = get_user_model().objects.filter(pk=int(brute), is_active=True).first()
        if user is None:
            raise ValueError('collaborateur inconnu')
        return user.pk
    return brute


def valider_donnees(type_demande, donnees, complet=False):
    """
    Normalise les champs du formulaire. complet=True (soumission) : les champs
    obligatoires doivent être renseignés. Les codes inconnus sont ignorés.
    """
    if not isinstance(donnees, dict):
        raise ErreurMetier({'donnees': 'Format invalide.'})
    erreurs, propres = {}, {}
    for champ in type_demande.champs.filter(actif=True):
        brute = donnees.get(champ.code)
        if brute in (None, '') or (isinstance(brute, str) and not brute.strip()):
            if complet and champ.obligatoire:
                erreurs[champ.code] = f"« {champ.libelle} » est obligatoire."
            continue
        try:
            propres[champ.code] = _valeur(champ, brute)
        except (ValueError, TypeError, InvalidOperation):
            erreurs[champ.code] = f"« {champ.libelle} » : valeur invalide."
    if erreurs:
        raise ErreurMetier({'donnees': erreurs})
    return propres


def valider_contenu(type_demande, donnees, complet=False):
    """Champs du formulaire + données propres à la famille (ex. `mission`)."""
    donnees = donnees or {}
    erreurs, propres = {}, {}
    try:
        propres = valider_donnees(type_demande, donnees, complet)
    except ErreurMetier as e:
        erreurs.update(e.detail)
    try:
        propres.update(extensions.pour(type_demande).valider(type_demande, donnees, complet))
    except ErreurMetier as e:
        erreurs.update(e.detail)
    if erreurs:
        raise ErreurMetier(erreurs)
    return propres


def _montant(brut):
    if brut in (None, ''):
        return None
    try:
        valeur = Decimal(str(brut).replace(' ', '').replace(',', '.')).quantize(Decimal('0.01'))
    except InvalidOperation:
        raise ErreurMetier({'montant_demande': 'Montant invalide.'})
    if valeur < 0:
        raise ErreurMetier({'montant_demande': 'Le montant ne peut pas être négatif.'})
    return valeur


def contexte_conditions(demande):
    """Valeurs lues par les conditions du workflow (données figées de la demande)."""
    ctx = {
        'type_demande': demande.type_demande.code,
        'montant_demande_ref': demande.montant_demande_ref if demande.montant_demande_ref is not None
        else demande.montant_demande,
        'categorie': demande.categorie_id, 'departement': demande.departement_id, 'agence': demande.agence_id,
        'departement__arbre': ([demande.departement_id] + [a.pk for a in demande.departement.ancetres()])
        if demande.departement_id else [],
    }
    for code, valeur in (demande.donnees or {}).items():
        if not isinstance(valeur, dict):
            ctx[f'champ.{code}'] = valeur
    ctx.update(extensions.pour(demande.type_demande).contexte(demande))
    return ctx


# ═══════════════════════════════════════════════════════════════
# DROITS
# ═══════════════════════════════════════════════════════════════

def est_valideur(demande, user):
    """A (ou a eu) une tâche sur la demande, directement ou par délégation en cours."""
    taches = Tache.objects.filter(etape_instance__instance__demande=demande)
    return taches.filter(moteur.filtre_taches_de(user)).exists() or taches.filter(traitee_par=user).exists()


def peut_voir(demande, user):
    return (demande.demandeur_id == user.pk or demande.cree_par_id == user.pk
            or voit_toutes_les_demandes(user) or est_valideur(demande, user))


def demandes_visibles(user):
    if voit_toutes_les_demandes(user):
        return Demande.objects.all()
    mes_taches = Tache.objects.filter(moteur.filtre_taches_de(user) | Q(traitee_par=user))
    return Demande.objects.filter(
        Q(demandeur=user) | Q(cree_par=user)
        | Q(pk__in=mes_taches.values('etape_instance__instance__demande'))).distinct()


def _exiger_demandeur(demande, user, statuts, action):
    if demande.demandeur_id != user.pk:
        raise Interdit(f"Seul le demandeur peut {action}.")
    if demande.statut not in statuts:
        raise ErreurMetier(f"Impossible de {action} une demande « {demande.get_statut_display()} ».")


# ═══════════════════════════════════════════════════════════════
# DEMANDE RATTACHÉE (frais complémentaires, annulation)
# ═══════════════════════════════════════════════════════════════

EN_COURS = (StatutDemande.BROUILLON, StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER)


def regle_parent(type_demande):
    """{types: [...] | '*', statuts: [...], unique_en_cours: bool} ou None (type sans rattachement)."""
    return (type_demande.parametres or {}).get('parent')


def parents_possibles(type_demande, user):
    regle = regle_parent(type_demande)
    if not regle:
        return Demande.objects.none()
    qs = Demande.objects.filter(demandeur=user, statut__in=regle.get('statuts', [StatutDemande.APPROUVEE])) \
        .exclude(type_demande__famille='annulation').select_related('type_demande')
    if regle.get('types', '*') != '*':
        qs = qs.filter(type_demande__code__in=regle['types'])
    if regle.get('unique_en_cours'):
        en_cours = Demande.objects.filter(type_demande=type_demande, statut__in=EN_COURS, demande_parent__isnull=False)
        qs = qs.exclude(pk__in=en_cours.values('demande_parent'))
    return qs.order_by('-approuvee_le', '-id')


def controler_parent(type_demande, parent, user, demande=None):
    regle = regle_parent(type_demande)
    if not regle:
        return None
    if parent is None:
        raise ErreurMetier({'demande_parent': 'Choisissez la demande concernée.'})
    if parent.demandeur_id != user.pk:
        raise Interdit("La demande concernée doit être l'une de vos demandes.")
    nom_parent = parent.reference or 'ce brouillon'
    if parent.type_demande.famille == 'annulation' or (
            regle.get('types', '*') != '*' and parent.type_demande.code not in regle['types']):
        raise ErreurMetier({'demande_parent': f"{nom_parent} ne peut pas être rattachée à ce type de demande."})
    statuts = regle.get('statuts', [StatutDemande.APPROUVEE])
    if parent.statut not in statuts:
        raise ErreurMetier({'demande_parent': f"{nom_parent} est « {parent.get_statut_display()} » : elle doit être "
                                              f"{' ou '.join(StatutDemande(s).label.lower() for s in statuts)}."})
    if regle.get('unique_en_cours'):
        autres = Demande.objects.filter(demande_parent=parent, type_demande=type_demande, statut__in=EN_COURS)
        if demande is not None:
            autres = autres.exclude(pk=demande.pk)
        if autres.exists():
            raise ErreurMetier({'demande_parent': f"Une demande « {type_demande.libelle} » est déjà en cours pour "
                                                  f"{nom_parent}."})
    return parent


# ═══════════════════════════════════════════════════════════════
# BROUILLONS
# ═══════════════════════════════════════════════════════════════

def creer_brouillon(user, type_demande, objet='', montant_demande=None, devise='', donnees=None, infos=None,
                    demande_parent=None):
    if not type_demande.actif:
        raise ErreurMetier("Ce type de demande n'est pas disponible.")
    if moteur.version_publiee(type_demande) is None:
        raise ErreurMetier("Ce type de demande n'a pas encore de circuit de validation publié.")
    saisi = type_demande.avec_montant and not extensions.pour(type_demande).montant_calcule
    if not saisi:
        devise = ''
    parent = controler_parent(type_demande, demande_parent, user)
    with transaction.atomic():
        demande = Demande.objects.create(
            type_demande=type_demande, demandeur=user, cree_par=user, objet=(objet or '').strip()[:255],
            montant_demande=_montant(montant_demande) if saisi else None,
            devise=(devise or ParametreSysteme.charger().devise_reference).upper()[:3],
            donnees=valider_contenu(type_demande, donnees, complet=False), demande_parent=parent)
        moteur.tracer(demande, 'creation', auteur=user, infos=infos)
    return demande


def modifier(demande, user, objet=None, montant_demande=None, devise=None, donnees=None, champs=()):
    """Mise à jour du contenu de travail (brouillon ou correction). `champs` : clés envoyées."""
    _exiger_demandeur(demande, user, {StatutDemande.BROUILLON, StatutDemande.A_CORRIGER}, 'modifier')
    if 'objet' in champs:
        demande.objet = (objet or '').strip()[:255]
    saisi = demande.type_demande.avec_montant and not extensions.pour(demande.type_demande).montant_calcule
    if 'montant_demande' in champs and saisi:
        demande.montant_demande = _montant(montant_demande)
    if 'devise' in champs and devise and saisi:
        if demande.statut != StatutDemande.BROUILLON and devise.upper() != demande.devise:
            raise ErreurMetier("La devise ne peut plus être changée après la première soumission.")
        demande.devise = devise.upper()
    if 'donnees' in champs:
        demande.donnees = valider_contenu(demande.type_demande, {**demande.donnees, **(donnees or {})}, complet=False)
    demande.save()
    return demande


def supprimer_brouillon(demande, user):
    _exiger_demandeur(demande, user, {StatutDemande.BROUILLON}, 'supprimer')
    if demande.reference or demande.versions.exists():
        raise ErreurMetier("Une demande déjà soumise ne peut pas être supprimée : annulez-la.")
    with transaction.atomic():
        fichiers = [d.fichier for d in demande.documents.all()]
        demande.documents.all().delete()
        demande.delete()
    for f in fichiers:
        f.delete(save=False)


# ═══════════════════════════════════════════════════════════════
# SOUMISSION
# ═══════════════════════════════════════════════════════════════

def _numero(type_demande):
    annee = timezone.localdate().year
    compteur, _ = CompteurReference.objects.select_for_update().get_or_create(type_demande=type_demande, annee=annee)
    compteur.dernier_numero += 1
    compteur.save(update_fields=['dernier_numero'])
    return f"{type_demande.prefixe_reference}-{annee}-{compteur.dernier_numero:05d}"


def _controler_contenu(demande):
    erreurs = {}
    if not demande.objet.strip():
        erreurs['objet'] = "L'objet est obligatoire."
    saisi = demande.type_demande.avec_montant and not extensions.pour(demande.type_demande).montant_calcule
    if saisi and (demande.montant_demande is None or demande.montant_demande <= 0):
        erreurs['montant_demande'] = 'Le montant est obligatoire.'
    try:
        demande.donnees = valider_contenu(demande.type_demande, demande.donnees, complet=True)
    except ErreurMetier as e:
        erreurs.update(e.detail)
    if erreurs:
        raise ErreurMetier(erreurs)
    pieces = {d.type_piece_id for d in demande.documents.filter(retire=False)}
    manquantes = [e.type_piece.libelle for e in demande.type_demande.exigences.filter(
        moment='soumission', obligatoire=True).select_related('type_piece') if e.type_piece_id not in pieces]
    if manquantes:
        raise ErreurMetier({'documents': f"Pièce(s) obligatoire(s) manquante(s) : {', '.join(manquantes)}."})


def verifier_pieces_etape(demande, etape):
    pieces = {d.type_piece_id for d in demande.documents.filter(retire=False)}
    manquantes = [e.type_piece.libelle for e in demande.type_demande.exigences.filter(
        moment='etape', etape_code=etape.code, obligatoire=True).select_related('type_piece')
        if e.type_piece_id not in pieces]
    if manquantes:
        raise ErreurMetier(f"Pièce(s) à joindre avant de valider cette étape : {', '.join(manquantes)}.")


def _figer_organisation(demande, d):
    """Copie la situation du demandeur à la date de soumission (première soumission)."""
    u = demande.demandeur
    demande.departement = org.departement_de(u, d)
    demande.agence = org.valeur_en_cours(u, 'agence', d)
    demande.categorie = org.valeur_en_cours(u, 'categorie', d)
    demande.poste = org.valeur_en_cours(u, 'poste', d)
    demande.n_plus_1 = org.n_plus_1(u, d).responsable
    demande.devise_reference = ParametreSysteme.charger().devise_reference
    demande.parametres_figes = {}


def _convertir_montant(demande, d):
    """
    Montant en devise de référence, au taux figé à la première soumission
    (la devise ne change plus ensuite).
    """
    from baremes import services as baremes
    if demande.montant_demande is None:
        demande.montant_demande_ref = None
        return
    ref = demande.devise_reference
    if demande.devise == ref:
        demande.montant_demande_ref = demande.montant_demande
        return
    figes = dict(demande.parametres_figes or {})
    t = (figes.get('taux') or {}).get(demande.devise) or baremes.taux(demande.devise, d, ref)
    if t is None:
        raise ErreurMetier({'devise': f"Aucun taux de change n'est défini pour la devise {demande.devise} : "
                                      f"saisissez le montant en {ref} ou demandez la création du taux."})
    figes['taux'] = {**(figes.get('taux') or {}), demande.devise: t}
    demande.parametres_figes = figes
    demande.montant_demande_ref = baremes.convertir(demande.montant_demande, t)


def preparer_soumission(demande, user):
    """
    Contrôles et plan de validation, sans rien enregistrer (première étape
    de la soumission).
    """
    _exiger_demandeur(demande, user, {StatutDemande.BROUILLON, StatutDemande.A_CORRIGER}, 'soumettre')
    d = timezone.localdate()
    premiere = demande.statut == StatutDemande.BROUILLON
    if premiere:
        version = moteur.version_publiee(demande.type_demande)
        if version is None:
            raise ErreurMetier("Ce type de demande n'a pas de circuit de validation publié.")
        _figer_organisation(demande, d)
    else:
        version = demande.version_workflow
    _controler_contenu(demande)
    if regle_parent(demande.type_demande):
        controler_parent(demande.type_demande, demande.demande_parent, user, demande)
    ext = extensions.pour(demande.type_demande)
    demande._calcul, demande._note_calcul = ext.avant_soumission(demande, d, premiere)
    if not ext.montant_calcule:
        _convertir_montant(demande, d)
    plan = moteur.calculer_plan(version, demande, d, contexte_conditions(demande))
    return version, plan


def _etapes_reprises(demande, version, plan):
    """
    Étapes déjà approuvées reprises après correction (§5.5) : si la version
    l'autorise, qu'aucun champ sensible ni le montant n'a changé et que le
    circuit jusqu'à l'étape du retour est identique.
    """
    precedente = demande.instances.order_by('-cycle').first()
    if (version.reprise_apres_correction != 'etape_retour_autorisee' or precedente is None
            or precedente.etat != 'retournee' or precedente.etape_retour_id is None):
        return set(), None
    ancienne = demande.version_courante
    sensibles = set(demande.type_demande.champs.filter(sensible=True).values_list('code', flat=True))
    if ancienne is None or ancienne.montant_demande != demande.montant_demande or any(
            ancienne.donnees.get(c) != demande.donnees.get(c) for c in sensibles) or \
            extensions.pour(demande.type_demande).modification_sensible(ancienne.donnees, demande.donnees):
        return set(), 'Modification sensible : reprise du circuit à la première étape.'
    ordre_retour = precedente.etape_retour.ordre
    avant = lambda p: [(e['etape'], e['statut']) for e in p if e['ordre'] < ordre_retour]
    if avant(plan) != avant(precedente.plan):
        return set(), 'Le circuit a changé : reprise à la première étape.'
    approuvees = set(precedente.etapes.filter(etat='approuvee', ordre__lt=ordre_retour)
                     .values_list('etape_id', flat=True))
    return approuvees, f"Reprise à l'étape « {precedente.etape_retour.libelle} » (aucune modification sensible)."


def soumettre(demande, user, motif='', infos=None):
    """Soumission (brouillon) ou resoumission (à corriger). Renvoie la demande."""
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        version, plan = preparer_soumission(demande, user)
        bloquages = moteur.blocages(plan)
        if bloquages:
            raise ErreurMetier({'circuit': bloquages})
        premiere = demande.statut == StatutDemande.BROUILLON
        reprises, note_reprise = (set(), None) if premiere else _etapes_reprises(demande, version, plan)
        if premiere:
            demande.reference = _numero(demande.type_demande)
            demande.version_workflow = version
            demande.soumise_le = timezone.now()
        precedente = demande.version_courante
        contenu = VersionContenu.objects.create(
            demande=demande, numero=(precedente.numero + 1) if precedente else 1,
            origine='soumission' if premiere else 'resoumission', objet=demande.objet,
            montant_demande=demande.montant_demande, devise=demande.devise, donnees=demande.donnees,
            calcul=demande._calcul or {}, motif_modification=motif or '', cree_par=user)
        extensions.pour(demande.type_demande).apres_version(demande, contenu)
        demande.documents.filter(version_contenu__isnull=True).update(version_contenu=contenu)
        demande.version_courante = contenu
        demande.statut = StatutDemande.EN_VALIDATION
        demande.montant_approuve = None
        demande.statut_financier = StatutFinancier.SANS_OBJET
        demande.save()
        cycle = demande.instances.count() + 1
        moteur.tracer(demande, 'soumission' if premiere else 'resoumission', auteur=user, infos=infos,
                      motif=' '.join(x for x in (motif, demande._note_calcul or '', note_reprise or '') if x),
                      donnees={'version_contenu': contenu.numero, 'cycle': cycle})
        if premiere:
            notifier([user], 'demande_soumise', f"{demande.reference} soumise",
                     f"Votre demande « {demande.objet} » est en cours de validation.", demande)
        moteur.demarrer(demande, version, plan, cycle, timezone.localdate(), reprise=reprises, infos=infos)
    demande.refresh_from_db()
    return demande


def alerter_blocage(demande, raisons):
    """Soumission bloquée par le paramétrage : alerte aux administrateurs (hors transaction)."""
    notifier(administrateurs(), 'workflow_bloque', f"Soumission bloquée : {demande.type_demande.libelle}",
             f"Demande de {moteur.nom(demande.demandeur)} : {' '.join(raisons)}", demande)


# ═══════════════════════════════════════════════════════════════
# ANNULATION, DUPLICATION, COMMENTAIRES
# ═══════════════════════════════════════════════════════════════

def annuler(demande, user, motif, infos=None):
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier("Le motif d'annulation est obligatoire.")
    with transaction.atomic():
        demande = Demande.objects.select_for_update().get(pk=demande.pk)
        autorises = set(demande.type_demande.annulation_demandeur or [])
        _exiger_demandeur(demande, user, {StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER}, 'annuler')
        if demande.statut not in autorises:
            raise ErreurMetier(f"Ce type de demande ne peut pas être annulé au statut "
                               f"« {demande.get_statut_display()} ».")
        instance = demande.instances.filter(etat='en_cours').first()
        if instance:
            moteur.annuler_instance(instance, user, motif, infos)
        demande.statut, demande.annulee_le, demande.motif_annulation = StatutDemande.ANNULEE, timezone.now(), motif
        demande.save()
        moteur.tracer(demande, 'annulation', auteur=user, motif=motif, infos=infos, instance=instance)
    return demande


def dupliquer(demande, user, infos=None):
    """Nouveau brouillon à partir d'une demande (rejetée, annulée…) ; pièces non recopiées."""
    if demande.demandeur_id != user.pk:
        raise Interdit("Seul le demandeur peut dupliquer sa demande.")
    if demande.statut == StatutDemande.BROUILLON:
        raise ErreurMetier("Un brouillon n'a pas besoin d'être dupliqué.")
    with transaction.atomic():
        copie = creer_brouillon(user, demande.type_demande, demande.objet, demande.montant_demande,
                                demande.devise, demande.donnees, infos, demande_parent=demande.demande_parent)
        copie.origine_copie = demande
        copie.save(update_fields=['origine_copie'])
        moteur.tracer(copie, 'duplication', auteur=user, infos=infos,
                      motif=f"Copie de {demande.reference or 'brouillon'}")
    return copie


def commenter(demande, user, texte, infos=None):
    from .models import Commentaire
    texte = (texte or '').strip()
    if not texte:
        raise ErreurMetier("Le commentaire est vide.")
    if not peut_voir(demande, user):
        raise Interdit("Vous n'avez pas accès à cette demande.")
    with transaction.atomic():
        c = Commentaire.objects.create(demande=demande, auteur=user, texte=texte[:5000])
        moteur.tracer(demande, 'commentaire', auteur=user, motif=texte[:5000], infos=infos)
        autres = [demande.demandeur] + [t.valideur for t in Tache.objects.filter(
            etape_instance__instance__demande=demande).select_related('valideur')]
        notifier([u for u in autres if u.pk != user.pk], 'commentaire', f"{demande.reference} : nouveau commentaire",
                 f"{moteur.nom(user)} : {texte[:200]}", demande)
    return c


# ═══════════════════════════════════════════════════════════════
# PIÈCES JOINTES
# ═══════════════════════════════════════════════════════════════

def _a_une_tache_en_attente(demande, user):
    return Tache.objects.filter(etape_instance__instance__demande=demande, etat='en_attente').filter(
        moteur.filtre_taches_de(user)).exists()


def peut_ajouter_document(demande, user):
    if demande.demandeur_id == user.pk and demande.statut in (StatutDemande.BROUILLON, StatutDemande.A_CORRIGER):
        return True
    return demande.statut == StatutDemande.EN_VALIDATION and _a_une_tache_en_attente(demande, user)


def creer_document(demande, user, fichier, type_piece=None, remplace=None):
    """Contrôle (format, taille) et enregistrement d'une pièce ; les droits sont vérifiés par l'appelant."""
    extension = fichier.name.rsplit('.', 1)[-1].lower() if '.' in fichier.name else ''
    if extension not in EXTENSIONS_AUTORISEES:
        raise ErreurMetier("Format non accepté (PDF, images, documents Office).")
    taille_max = ParametreSysteme.charger().taille_max_piece_mo * 1024 * 1024
    if fichier.size > taille_max:
        raise ErreurMetier(f"La pièce ne doit pas dépasser {taille_max // (1024 * 1024)} Mo.")
    empreinte = hashlib.sha256()
    for morceau in fichier.chunks():
        empreinte.update(morceau)
    fichier.seek(0)
    en_cours = demande.statut in (StatutDemande.BROUILLON, StatutDemande.A_CORRIGER)
    return Document.objects.create(
        demande=demande, type_piece=type_piece, fichier=fichier, nom_origine=fichier.name[:255],
        taille=fichier.size, empreinte=empreinte.hexdigest(), ajoute_par=user, remplace=remplace,
        version_contenu=None if en_cours else demande.version_courante)


def ajouter_document(demande, user, fichier, type_piece=None, remplace=None, infos=None):
    if not peut_ajouter_document(demande, user):
        raise Interdit("Vous ne pouvez pas ajouter de pièce à cette demande à ce stade.")
    with transaction.atomic():
        doc = creer_document(demande, user, fichier, type_piece, remplace)
        if remplace is not None:
            retirer_document(remplace, user, f"Remplacé par « {doc.nom_origine} »", infos, _depuis_remplacement=True)
        if demande.reference:
            moteur.tracer(demande, 'document', auteur=user, infos=infos,
                          motif=f"Pièce ajoutée : {doc.nom_origine}", donnees={'document': doc.pk})
    return doc


def retirer_document(doc, user, motif='', infos=None, _depuis_remplacement=False):
    """Brouillon jamais soumis : suppression ; sinon retrait logique motivé (pièce conservée)."""
    demande = doc.demande
    if doc.retire:
        raise ErreurMetier("Cette pièce est déjà retirée.")
    if doc.ajoute_par_id != user.pk:
        raise Interdit("Seule la personne qui a ajouté la pièce peut la retirer.")
    if not _depuis_remplacement and not peut_ajouter_document(demande, user):
        raise ErreurMetier("Les pièces ne peuvent plus être modifiées à ce stade.")
    if doc.version_contenu_id is None and not demande.reference:
        fichier = doc.fichier
        doc.delete()
        fichier.delete(save=False)
        return None
    motif = (motif or '').strip()
    if not motif:
        raise ErreurMetier("Le motif du retrait est obligatoire.")
    doc.retire, doc.retire_le, doc.retire_par, doc.motif_retrait = True, timezone.now(), user, motif[:255]
    doc.save()
    moteur.tracer(demande, 'document', auteur=user, infos=infos, motif=f"Pièce retirée : {doc.nom_origine} — {motif}",
                  donnees={'document': doc.pk, 'retrait': True})
    return doc


def peut_telecharger(doc, user):
    return peut_voir(doc.demande, user)


# ═══════════════════════════════════════════════════════════════
# ACTIONS DISPONIBLES (pour les écrans)
# ═══════════════════════════════════════════════════════════════

def actions_possibles(demande, user):
    from tresorerie.services import annulation_en_cours, peut_payer
    s = demande.statut
    demandeur = demande.demandeur_id == user.pk
    approuvee = s in (StatutDemande.APPROUVEE, StatutDemande.EN_ATTENTE_CLOTURE)
    return {
        'payer': peut_payer(demande, user) and annulation_en_cours(demande) is None,
        'demander_annulation': demandeur and approuvee and demande.type_demande.famille != 'annulation'
                               and annulation_en_cours(demande) is None,
        'frais_complementaires': demandeur and approuvee and demande.type_demande.famille == 'mission',
        'modifier': demandeur and s in (StatutDemande.BROUILLON, StatutDemande.A_CORRIGER),
        'soumettre': demandeur and s in (StatutDemande.BROUILLON, StatutDemande.A_CORRIGER),
        'supprimer': demandeur and s == StatutDemande.BROUILLON and not demande.reference,
        'annuler': demandeur and s in (StatutDemande.EN_VALIDATION, StatutDemande.A_CORRIGER)
                   and s in (demande.type_demande.annulation_demandeur or []),
        'dupliquer': demandeur and s != StatutDemande.BROUILLON,
        'ajouter_document': peut_ajouter_document(demande, user),
        'commenter': True,
    }
