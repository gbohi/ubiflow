"""
Jours d'ouverture des agences : planning des menus, accueils et alertes
« menu manquant » suivent les jours cochés (lundi → vendredi par défaut).

Lancer : python manage.py test api.tests_jours_ouverture
"""
from datetime import timedelta

from django.utils import timezone

from .models import Agence, Menu
from .tests import API, _EspacePrestataireBase


class JoursOuvertureTests(_EspacePrestataireBase):

    def _lundi_prochain(self):
        d = timezone.localdate()
        return d - timedelta(days=d.weekday()) + timedelta(days=7)

    def test_defaut_lundi_vendredi_et_validation(self):
        self.assertEqual(Agence.objects.create(nom_agence='Test').jours_ouverture, [0, 1, 2, 3, 4])
        a = self.client_pour(self.admin)
        r = a.patch(f'{API}/agences/{self.agence.id}/', {'jours_ouverture': [5, 0, 1, 2, 3, 4, 4]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['jours_ouverture'], [0, 1, 2, 3, 4, 5])
        self.assertEqual(a.patch(f'{API}/agences/{self.agence.id}/', {'jours_ouverture': [7]},
                                 format='json').status_code, 400)
        self.assertEqual(a.patch(f'{API}/agences/{self.agence.id}/', {'jours_ouverture': []},
                                 format='json').status_code, 400)

    def test_planning_avec_samedi(self):
        lundi = self._lundi_prochain()
        g = self.client_pour(self.admin)
        r = g.get(f'{API}/planning/', {'debut': lundi.isoformat()})
        self.assertEqual(len(r.data['jours']), 5)                        # comme avant
        self.agence.jours_ouverture = [0, 1, 2, 3, 4, 5]
        self.agence.save()
        r = g.get(f'{API}/planning/', {'debut': lundi.isoformat()})
        self.assertEqual(len(r.data['jours']), 6)                        # + samedi
        ag = next(a for a in r.data['agences'] if a['id'] == self.agence.id)
        self.assertTrue(ag['jours'][5]['ouvert'])
        autres = [a for a in r.data['agences'] if a['id'] != self.agence.id]
        self.assertTrue(all(not a['jours'][5]['ouvert'] for a in autres))

    def test_menu_exceptionnel_un_dimanche_reste_visible(self):
        lundi = self._lundi_prochain()
        Menu.objects.create(date_menu=lundi + timedelta(days=6), agence=self.agence, typeequipe=self.typeequipe)
        r = self.client_pour(self.admin).get(f'{API}/planning/', {'debut': lundi.isoformat()})
        self.assertEqual(r.data['jours'][-1]['date'], lundi + timedelta(days=6))

    def test_contexte_prestataire_jours(self):
        self.agence.jours_ouverture = [0, 1, 2, 3, 4, 5]
        self.agence.save()
        r = self.client_pour(self.agent_a).get(f'{API}/prestataire/contexte/')
        ag = next(a for a in r.data['agences'] if a['id'] == self.agence.id)
        self.assertEqual(ag['jours_ouverture'], [0, 1, 2, 3, 4, 5])

    def test_alerte_menu_manquant_le_samedi(self):
        # Jours de semaine des 7 prochains jours avec menu : seul le samedi peut manquer
        aujourdhui = timezone.localdate()
        for i in range(1, 8):
            d = aujourdhui + timedelta(days=i)
            if d.weekday() < 5:
                Menu.objects.create(date_menu=d, agence=self.agence, typeequipe=self.typeequipe)
        g = self.client_pour(self.gestionnaire)
        titres = lambda: [a['titre'] for a in g.get(f'{API}/accueil/').data['gestion']['a_faire']
                          if a['type'] == 'menu_manquant']
        self.assertFalse(any('samedi' in t for t in titres()))
        self.agence.jours_ouverture = [0, 1, 2, 3, 4, 5]
        self.agence.save()
        self.assertTrue(any('samedi' in t for t in titres()))
