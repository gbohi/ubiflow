"""Lot 6 : calendrier ouvré, échéances, rappels, escalades, rappels de clôture."""
from datetime import date, datetime, timedelta

from django.core.management import call_command
from django.utils import timezone

from api import calendrier
from api.models import JourFerie
from notifications.models import Notification

from .models import Action, Tache
from .tests import Base


def t(*a):
    return timezone.make_aware(datetime(*a))


class CalendrierTests(Base):
    def test_heures_ouvrees(self):
        # vendredi 20/11/2026 18h → lundi 23/11/2026 18h : 6 h vendredi + 18 h lundi
        self.assertEqual(calendrier.heures_ouvrees(t(2026, 11, 20, 18), t(2026, 11, 23, 18)), 24)
        JourFerie.objects.get_or_create(date=date(2026, 11, 23), defaults={'libelle': 'test'})
        self.assertEqual(calendrier.heures_ouvrees(t(2026, 11, 20, 18), t(2026, 11, 23, 18)), 6)
        # 30 h ouvrées depuis vendredi 18h, lundi férié → mardi 24 à 0h + 24 h = mercredi 25 à 0h
        self.assertEqual(calendrier.ajouter_heures_ouvrees(t(2026, 11, 20, 18), 30), t(2026, 11, 25, 0))


class RappelsTests(Base):
    def test_echeance_rappel_et_escalade(self):
        etape = self.v1.etapes.get(code='n_plus_1')
        etape.delai_heures, etape.rappel_apres_heures, etape.escalade_apres_heures = 24, 24, 48
        etape.escalade_vers = 'personne'
        etape.escalade_personne = self.dg
        etape.save()
        pk = self.creer()
        self.soumettre(pk)
        tache = self.tache_de(pk, self.chef)
        self.assertIsNotNone(tache.echeance)
        # ouverture reculée de 4 jours calendaires (au moins 48 h ouvrées)
        Tache.objects.filter(pk=tache.pk).update(ouverte_le=timezone.now() - timedelta(days=5),
                                                 echeance=timezone.now() - timedelta(days=3))
        call_command('taches_planifiees')
        tache.refresh_from_db()
        self.assertEqual((tache.rappels_envoyes, tache.escaladee), (1, True))
        self.assertTrue(Notification.objects.filter(destinataire=self.chef, evenement='rappel').exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.dg, evenement='escalade').exists())
        self.assertTrue(Action.objects.filter(demande_id=pk, type='escalade').exists())
        call_command('taches_planifiees')  # pas de second rappel dans les 24 h, pas de nouvelle escalade
        tache.refresh_from_db()
        self.assertEqual(tache.rappels_envoyes, 1)
        self.en(self.chef)
        r = self.client.get('/api/api/taches/')
        self.assertTrue(r.data['results'][0]['en_retard'])

    def test_sans_delai_rien_ne_se_passe(self):
        pk = self.creer()
        self.soumettre(pk)
        Tache.objects.filter(etape_instance__instance__demande_id=pk).update(ouverte_le=timezone.now() - timedelta(days=30))
        call_command('taches_planifiees')
        self.assertFalse(Notification.objects.filter(evenement__in=['rappel', 'escalade']).exists())
