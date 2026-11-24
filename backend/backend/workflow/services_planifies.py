"""
Traitements périodiques (§5.8, §9) lancés par la commande `taches_planifiees`
(conteneur « planificateur », toutes les heures) :
- rappel au valideur après `rappel_apres_heures` ouvrées, puis chaque jour ;
- escalade après `escalade_apres_heures` ouvrées (N+1 du valideur,
  administrateurs des workflows ou personne désignée ; la tâche reste au valideur) ;
- rappel de clôture au demandeur `delai_cloture_jours` après le retour de mission, puis chaque semaine.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from api import calendrier, organisation as org
from notifications.services import notifier

from . import moteur
from .models import Tache


def destinataires_escalade(tache):
    etape = tache.etape_instance.etape
    if etape.escalade_vers == 'personne' and etape.escalade_personne_id:
        return [etape.escalade_personne]
    if etape.escalade_vers == 'n_plus_1_valideur':
        n1 = org.n_plus_1(tache.valideur).responsable
        if n1:
            return [n1]
    User = get_user_model()
    return list(User.objects.filter(is_active=True, groups__name__in=['admin_workflow', 'admin', 'super_admin']).distinct())


def traiter_taches(maintenant=None):
    maintenant = maintenant or timezone.now()
    ctx = calendrier._contexte()
    rappels = escalades = 0
    qs = (Tache.objects.filter(etat='en_attente', ouverte_le__isnull=False)
          .select_related('valideur', 'etape_instance__etape', 'etape_instance__instance__demande'))
    for t in qs:
        etape = t.etape_instance.etape
        if not (etape.rappel_apres_heures or etape.escalade_apres_heures):
            continue
        ecoule = calendrier.heures_ouvrees(t.ouverte_le, maintenant, ctx)
        demande = t.etape_instance.instance.demande
        with transaction.atomic():
            if etape.rappel_apres_heures and ecoule >= etape.rappel_apres_heures and (
                    t.dernier_rappel is None or maintenant - t.dernier_rappel >= timedelta(hours=24)):
                retard = f" (échéance dépassée depuis le {timezone.localtime(t.echeance):%d/%m/%Y %H:%M})" \
                    if t.echeance and t.echeance < maintenant else ''
                notifier([t.valideur], 'rappel', f"Rappel : {demande.reference} attend votre validation",
                         f"Étape « {etape.libelle} » ouverte le {timezone.localtime(t.ouverte_le):%d/%m/%Y}{retard}.", demande)
                t.rappels_envoyes += 1
                t.dernier_rappel = maintenant
                t.save(update_fields=['rappels_envoyes', 'dernier_rappel'])
                rappels += 1
            if etape.escalade_apres_heures and ecoule >= etape.escalade_apres_heures and not t.escaladee:
                cibles = [u for u in destinataires_escalade(t) if u.pk != t.valideur_id]
                notifier(cibles, 'escalade', f"Escalade : {demande.reference} en attente chez {moteur.nom(t.valideur)}",
                         f"Étape « {etape.libelle} » sans décision depuis {int(ecoule)} h ouvrées. "
                         "Relancez le valideur ou faites réaffecter la validation.", demande)
                moteur.tracer(demande, 'escalade', instance=t.etape_instance.instance, etape_instance=t.etape_instance,
                              tache=t, motif=f"Escalade après {int(ecoule)} h ouvrées vers "
                                             f"{', '.join(moteur.nom(u) for u in cibles) or 'personne'}.")
                t.escaladee = True
                t.save(update_fields=['escaladee'])
                escalades += 1
    return rappels, escalades


def rappeler_clotures(maintenant=None):
    from missions.calcul import _date_heure
    from missions.models import ClotureMission
    from demandes.models import Demande
    maintenant = maintenant or timezone.now()
    n = 0
    for d in Demande.objects.filter(statut='en_attente_cloture', type_demande__famille='mission').select_related('type_demande', 'demandeur'):
        delai = d.type_demande.delai_cloture_jours
        mission = (d.donnees or {}).get('mission') or {}
        if delai is None or not mission.get('retour_le'):
            continue
        cloture, _ = ClotureMission.objects.get_or_create(demande=d)
        if cloture.etat not in ('brouillon', 'retournee'):
            continue
        retour = _date_heure(mission['retour_le'])
        if maintenant < retour + timedelta(days=delai):
            continue
        if cloture.dernier_rappel and maintenant - cloture.dernier_rappel < timedelta(days=7):
            continue
        notifier([d.demandeur], 'rappel_cloture', f"{d.reference} : clôture de mission attendue",
                 f"Votre mission est terminée depuis le {timezone.localtime(retour):%d/%m/%Y} : déclarez vos dépenses "
                 "réelles et joignez le rapport de mission.", d)
        cloture.dernier_rappel = maintenant
        cloture.save(update_fields=['dernier_rappel'])
        n += 1
    return n
