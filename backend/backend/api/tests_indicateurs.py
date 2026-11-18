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


class _IndicateursBase(_SupplementsBase):

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



class IndicateursTests(_IndicateursBase):

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


class ComplementsTests(_IndicateursBase):
    """Statistiques complémentaires sur le même jeu de données (2 repas, 1 dessert)."""

    def test_ubipharm_complements(self):
        from .models import Retrait, UserAgence
        m = Commande.objects.filter(commande_principale__isnull=True).first().menu
        Retrait.objects.create(user=self.employe, menu=m, badge_matricule='x', mode='badge',
                               date_retrait=timezone.make_aware(timezone.datetime.combine(self.jour,
                                                                                         timezone.datetime.min.time()))
                               + timedelta(hours=12, minutes=20))
        r = self.client_pour(self.admin).get(f'{API}/statistiques/complements/', self.params)
        self.assertEqual(r.status_code, 200, r.data)
        d = r.data
        self.assertEqual((d['desserts']['nb_repas'], d['desserts']['repas_avec_dessert']), (2, 1))
        self.assertEqual(d['desserts']['part_avec_dessert'], 50.0)
        self.assertEqual(d['desserts']['cout_offerts'], 300.0)
        self.assertEqual(d['affluence']['pointe']['tranche'], '12:15')
        self.assertTrue(d['participation']['effectif'] >= 2)
        self.assertEqual(d['prestataires'][0]['repas'], 2)
        self.assertIn('par_mois', d['comptes_repas'])
        self.assertEqual(d['controle']['contestations'], 0)
        self.assertEqual(d['jeux']['parties'], 0)
        self.assertEqual(self.client_pour(self.employe).get(f'{API}/statistiques/complements/').status_code, 403)

    def test_prestataire_complements(self):
        r = self.client_pour(self.resp_a).get(f'{API}/prestataire/statistiques/indicateurs/', self.params).data
        self.assertEqual(r['complements']['desserts']['nb_desserts'], 1)
        self.assertIn('tranches', r['complements']['affluence'])


class RapportMensuelTests(_IndicateursBase):

    def test_pdf_et_notification(self):
        from unittest.mock import patch
        from .models import Notification
        from .pdf_rapport import notifier_rapport_mensuel
        r = self.client_pour(self.admin).get(f'{API}/statistiques/rapport-mensuel/',
                                             {'annee': self.jour.year, 'mois': self.jour.month})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertEqual(self.client_pour(self.employe).get(f'{API}/statistiques/rapport-mensuel/').status_code, 403)
        premier = timezone.localtime().replace(day=1, hour=8)
        with patch('api.pdf_rapport.timezone.localtime', return_value=premier), \
                patch('api.fcm_service.messaging', create=True):
            n1 = notifier_rapport_mensuel()
            n2 = notifier_rapport_mensuel()
        self.assertGreaterEqual(n1, 1)
        self.assertEqual(n2, 0)                       # une seule fois par mois
        self.assertTrue(Notification.objects.filter(user=self.admin, donnees__has_key='rapport_mensuel').exists())
