"""
Indicateurs des plats et montants (Statistiques UbiPharm et prestataire).

Lancer : python manage.py test api.tests_indicateurs
"""
from datetime import timedelta
from decimal import Decimal as D

from django.utils import timezone

from .models import Commande, Menu, MenuPlat
from .tests import API
from .tests_supplements import _SupplementsBase


class IndicateursTests(_SupplementsBase):

    def setUp(self):
        super().setUp()
        self.jour = timezone.localdate().replace(day=1) - timedelta(days=3)    # mois précédent
        m = Menu.objects.create(date_menu=self.jour, agence=self.agence, typeequipe=self.typeequipe,
                                prestataire=self.presta_a)
        for p in (self.plat_a, self.plat_c, self.salade):
            MenuPlat.objects.create(menu=m, plat=p)
        c1 = Commande.objects.create(user=self.employe, menu=m, plat=self.plat_a, statut='retiree',
                                     mode_paiement='retenue')
        Commande.objects.create(user=self.employe, menu=m, plat=self.salade, statut='retiree',
                                mode_paiement='offert', commande_principale=c1)
        Commande.objects.create(user=self.employe2, menu=m, plat=self.plat_c, statut='retiree',
                                mode_paiement='retenue')
        self.params = {'debut': self.jour.replace(day=1).isoformat(), 'fin': self.jour.isoformat()}

    def test_ubipharm(self):
        r = self.client_pour(self.admin).get(f'{API}/statistiques/indicateurs/', self.params)
        self.assertEqual(r.status_code, 200, r.data)
        d = r.data
        self.assertEqual((d['kpis']['nb_repas'], d['kpis']['nb_supplements'], d['kpis']['nb_menus']), (2, 1, 1))
        self.assertEqual({p['plat'] for p in d['par_plat']}, {self.plat_a.nom, self.plat_c.nom})
        self.assertEqual(sum(p['popularite'] for p in d['par_plat']), 100.0)
        self.assertEqual(d['par_menu'][0]['commandes'], 2)
        self.assertEqual(d['preferences']['agences'][0]['agence'], self.agence.nom_agence)
        mt = d['montants']
        self.assertEqual(mt['total_employes'], 2500.0)               # 1 000 (standard) + 1 500 (complet)
        self.assertEqual(mt['total_prestataires'], 2500.0)           # 900 + 1 300 + dessert 300
        self.assertEqual(sum(x['prestataires'] for x in mt['par_mois']), 2500.0)
        self.assertIn('Dessert', {t['type_plat'] for t in mt['par_type']})
        self.assertEqual(mt['par_mode'][0]['mode'], 'retenue')
        self.assertEqual(self.client_pour(self.employe).get(f'{API}/statistiques/indicateurs/').status_code, 403)

    def test_prestataire_sans_montants_employes(self):
        r = self.client_pour(self.resp_a).get(f'{API}/prestataire/statistiques/indicateurs/', self.params)
        self.assertEqual(r.status_code, 200, r.data)
        mt = r.data['montants']
        self.assertNotIn('total_employes', mt)
        self.assertNotIn('par_mode', mt)
        self.assertEqual(mt['total_prestataires'], 2500.0)
        self.assertNotIn('employes', mt['par_agence'][0])
        self.assertEqual(self.client_pour(self.resp_b).get(f'{API}/prestataire/statistiques/indicateurs/',
                                                           self.params).data['kpis']['nb_repas'], 0)
        self.assertEqual(self.client_pour(self.agent_a).get(f'{API}/prestataire/statistiques/indicateurs/')
                         .status_code, 403)
