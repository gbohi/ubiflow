"""
Suppléments (desserts) : inclus pour l'employé, payés au prestataire, jamais
sans plat, un par jour, remplacés / retirés avant l'heure limite, annulés
avec le plat, retirés au comptoir avec lui, hors comptage des repas.

Lancer : python manage.py test api.tests_supplements
"""
from decimal import Decimal as D
from unittest.mock import patch

from . import comptes_repas as cr
from . import facturation as fact
from .models import Commande, FamilleSupplement, MenuPlat, Plat, PlatPrestataire, Retrait, TypePlat
from .tests import API, _synchrone
from .tests_tarifs_offerts import _TarifsBase


class _SupplementsBase(_TarifsBase):

    def setUp(self):
        super().setUp()
        self.famille = FamilleSupplement.objects.get(libelle='Dessert')    # créée par la migration 0054
        self.type_dessert = TypePlat.objects.create(libelle='Dessert', famille_supplement=self.famille)
        PlatPrestataire.objects.create(prestataire=self.presta_a, type_plat=self.type_dessert, montant=D('300'),
                                       statut=self.statut, date_debut=self.debut)
        self.banane = self._dessert('Banane flambée')
        self.salade = self._dessert('Salade de fruits')

    def _dessert(self, nom):
        p = Plat.objects.create(nom=nom, type_plat=self.type_dessert, agence=self.agence, prestataire=self.presta_a)
        p.agences.set([self.agence])
        return p

    def menu(self, jours=5, equipe=None):
        m = super().menu(jours, equipe)
        for p in (self.banane, self.salade):
            MenuPlat.objects.create(menu=m, plat=p)
        return m

    def commander(self, menu, plat, mode=None, user=None, supplements=None):
        donnees = {'menu_id': menu.id, 'plat_id': plat.id}
        if mode:
            donnees['mode_paiement'] = mode
        if supplements is not None:
            donnees['supplements'] = [p.id for p in supplements]
        with patch('api.signals._en_arriere_plan', _synchrone):
            return self.client_pour(user or self.employe).post(f'{API}/commandes/', donnees, format='json')



class SupplementsTests(_SupplementsBase):

    def test_plat_et_dessert_inclus_compte_debite_du_plat_seulement(self):
        cr.recharger(self.employe, D('5000'), self.admin)
        m = self.menu()
        r = self.commander(m, self.plat_a, 'compte', supplements=[self.salade])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data['supplements']), 1)
        self.assertTrue(r.data['supplements'][0]['inclus'])
        self.assertEqual(r.data['supplements'][0]['famille'], 'Dessert')
        self.assertEqual(cr.solde(self.employe), D('4000'))                # 1 000 F : le plat seul
        sup = Commande.objects.get(plat=self.salade)
        self.assertEqual((sup.mode_paiement, sup.commande_principale_id), ('offert', r.data['id']))
        # Facture de l'employé : 1 000 F ; relevé du prestataire : 900 F + dessert 300 F
        qs = Commande.objects.filter(user=self.employe)
        self.assertEqual(sum(l['montant'] or 0 for l in fact.lignes_facturation(qs)), D('1000'))
        self.assertEqual(sorted(l['montant'] for l in fact.lignes_prestataires(qs)), [D('300'), D('900')])

    def test_dessert_jamais_seul_et_un_par_jour(self):
        m = self.menu()
        r = self.commander(m, self.salade)
        self.assertEqual(r.status_code, 400)
        self.assertIn('plat principal', str(r.data))
        r = self.commander(m, self.plat_a, supplements=[self.salade, self.banane])
        self.assertEqual(r.status_code, 400)                              # 2 desserts : refusé, rien créé
        self.assertFalse(Commande.objects.filter(user=self.employe).exists())

    def test_changer_puis_retirer_le_dessert(self):
        m = self.menu()
        cid = self.commander(m, self.plat_a, supplements=[self.salade]).data['id']
        c = self.client_pour(self.employe)
        r = c.post(f'{API}/commandes/{cid}/supplement/', {'plat_id': self.banane.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([s['plat_detail']['nom'] for s in r.data['supplements']], ['Banane flambée'])
        self.assertEqual(Commande.objects.get(plat=self.salade).statut, 'annulee')
        # Revenir à la salade : la commande annulée est reprise (un même plat une fois par menu)
        r = c.post(f'{API}/commandes/{cid}/supplement/', {'plat_id': self.salade.id}, format='json')
        self.assertEqual([s['plat_detail']['nom'] for s in r.data['supplements']], ['Salade de fruits'])
        r = c.delete(f'{API}/commandes/{cid}/supplement/?famille={self.famille.id}')
        self.assertEqual(r.data['supplements'], [])
        self.assertEqual(self.client_pour(self.employe2).post(
            f'{API}/commandes/{cid}/supplement/', {'plat_id': self.banane.id}, format='json').status_code, 403)

    def test_annuler_le_plat_annule_le_dessert(self):
        m = self.menu()
        cid = self.commander(m, self.plat_a, supplements=[self.salade]).data['id']
        with patch('api.signals._en_arriere_plan', _synchrone):
            r = self.client_pour(self.employe).patch(f'{API}/commandes/{cid}/annuler/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Commande.objects.get(plat=self.salade).statut, 'annulee')

    def test_un_seul_repas_par_jour_et_listes(self):
        m = self.menu()
        self.commander(m, self.plat_a, supplements=[self.salade])
        self.assertEqual(self.commander(m, self.plat_c).status_code, 400)  # un repas par jour, inchangé
        mes = self.client_pour(self.employe).get(f'{API}/commandes/mes-commandes/').data
        self.assertEqual(len(mes), 1)                                     # dessert dans son plat
        self.assertEqual(mes[0]['supplements'][0]['plat_detail']['nom'], 'Salade de fruits')

    def test_retrait_au_comptoir_plat_et_dessert(self):
        from . import supplements as sp
        m = self.menu_du_jour(plats=[self.plat_a, self.salade, self.banane])   # commandes du jour : déjà closes
        principal = Commande.objects.create(user=self.employe, menu=m, plat=self.plat_a)
        sp.ajouter(principal, self.salade, self.employe, verifier_delai=False)
        agent = self.client_pour(self.agent_a)
        r = agent.get(f'{API}/prestataire/comptoir/recherche/', {'badge': self.employe.username})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['commandes']), 2)
        self.assertEqual(r.data['menu_id'], m.id)
        with patch('api.signals._en_arriere_plan', _synchrone):
            v = agent.post(f'{API}/prestataire/comptoir/valider/',
                           {'menu_id': m.id, 'user_id': self.employe.id, 'mode': 'saisie'}, format='json')
        self.assertIn(v.status_code, (200, 201), v.data)
        self.assertEqual(set(Commande.objects.filter(user=self.employe).values_list('statut', flat=True)), {'retiree'})
        self.assertEqual(Retrait.objects.count(), 1)
        s = agent.get(f'{API}/prestataire/comptoir/service/').data
        self.assertEqual((s['commandees'], s['servies']), (1, 1))          # le dessert n'est pas un repas

    def test_repas_offert_selon_la_famille(self):
        self.nuit.repas_offert = True
        self.nuit.save()
        m = self.menu(equipe=self.nuit)
        r = self.commander(m, self.plat_a, supplements=[self.salade])
        self.assertEqual(r.status_code, 201, r.data)
        Commande.objects.all().delete()
        self.famille.repas_offert = False
        self.famille.save()
        self.assertEqual(self.commander(m, self.plat_a, supplements=[self.salade]).status_code, 400)

    def test_familles_reservees_aux_administrateurs(self):
        self.assertEqual(self.client_pour(self.employe).get(f'{API}/supplements/familles/').status_code, 200)
        self.assertEqual(self.client_pour(self.gestionnaire).post(
            f'{API}/supplements/familles/', {'libelle': 'Boisson'}, format='json').status_code, 403)
        a = self.client_pour(self.admin)
        r = a.post(f'{API}/supplements/familles/', {'libelle': 'Boisson', 'inclus': False}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(a.delete(f'{API}/supplements/familles/{self.famille.id}/').status_code, 400)   # utilisée
        self.assertEqual(a.delete(f'{API}/supplements/familles/{r.data["id"]}/').status_code, 204)

    def test_parcours_desserts_a_part(self):
        m = self.menu()
        c = self.client_pour(self.employe)
        url = f'{API}/commander/jours/'
        params = {'agence': self.agence.id, 'prestataire': self.presta_a.id, 'semaine': m.date_menu.isoformat()}
        jour = next(j for j in c.get(url, params).data['jours'] if j['date'] == m.date_menu.isoformat())
        self.assertEqual({p['nom'] for p in jour['plats']}, {self.plat_a.nom, self.plat_c.nom})
        self.assertEqual({s['nom'] for s in jour['supplements']}, {'Banane flambée', 'Salade de fruits'})
        self.assertTrue(all(s['inclus'] and s['prix'] is None for s in jour['supplements']))
        self.commander(m, self.plat_a, supplements=[self.banane])
        jour = next(j for j in c.get(url, params).data['jours'] if j['date'] == m.date_menu.isoformat())
        self.assertEqual([s['nom'] for s in jour['supplements'] if s['choisi']], ['Banane flambée'])
        self.assertEqual(jour['commande']['supplements'][0]['plat'], 'Banane flambée')

    def test_supplements_proposes_pour_un_repas(self):
        m = self.menu()
        cid = self.commander(m, self.plat_a, supplements=[self.salade]).data['id']
        r = self.client_pour(self.employe).get(f'{API}/commandes/{cid}/supplement/')
        self.assertTrue(r.data['modifiable'])
        self.assertEqual({(s['nom'], s['choisi']) for s in r.data['supplements']},
                         {('Banane flambée', False), ('Salade de fruits', True)})
        self.assertEqual(self.client_pour(self.employe2).get(f'{API}/commandes/{cid}/supplement/').status_code, 403)


class SupplementsComptesAPartTests(_SupplementsBase):
    """Un plat + son dessert = 1 repas et 1 supplément (relevés, clôture, statistiques, liste du jour)."""

    def _mois_passe(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Menu
        jour = timezone.localdate().replace(day=1) - timedelta(days=3)
        m = Menu.objects.create(date_menu=jour, agence=self.agence, typeequipe=self.typeequipe,
                                prestataire=self.presta_a)
        for p in (self.plat_a, self.salade):
            MenuPlat.objects.create(menu=m, plat=p)
        c = Commande.objects.create(user=self.employe, menu=m, plat=self.plat_a, statut='retiree',
                                    mode_paiement='retenue')
        Commande.objects.create(user=self.employe, menu=m, plat=self.salade, statut='retiree',
                                mode_paiement='offert', commande_principale=c)
        return jour

    def test_cloture_et_releve(self):
        from .models import FacturePrestataire
        jour = self._mois_passe()
        cloture = fact.cloturer_mois(jour.year, jour.month, self.admin)
        self.assertEqual(cloture.nb_repas, 1)                         # facture employé : le plat seul
        f = FacturePrestataire.objects.get(prestataire=self.presta_a)
        self.assertEqual((f.nb_repas, f.nb_supplements, f.montant_total), (1, 1, D('1200')))
        rel = self.client_pour(self.resp_a).get(f'{API}/prestataire/releves/').data
        ligne = next(r for r in rel if r['etat'] == 'cloture')
        self.assertEqual((ligne['nb_repas'], ligne['nb_supplements']), (1, 1))

    def test_statistiques_prestataire(self):
        jour = self._mois_passe()
        debut = jour.replace(day=1).isoformat()
        r = self.client_pour(self.resp_a).get(f'{API}/prestataire/statistiques/',
                                              {'debut': debut, 'fin': jour.isoformat()}).data
        self.assertEqual((r['kpis']['commandes'], r['kpis']['supplements']), (1, 1))
        self.assertEqual([p['plat'] for p in r['par_plat']], [self.plat_a.nom])
        self.assertEqual([p['plat'] for p in r['par_supplement']], ['Salade de fruits'])

    def test_liste_du_jour_une_ligne_par_repas(self):
        from . import supplements as sp
        m = self.menu_du_jour(plats=[self.plat_a, self.salade])
        principal = Commande.objects.create(user=self.employe, menu=m, plat=self.plat_a)
        sp.ajouter(principal, self.salade, self.employe, verifier_delai=False)
        r = self.client_pour(self.agent_a).get(f'{API}/prestataire/liste-du-jour/').data
        self.assertEqual(r['total'], 1)
        self.assertEqual(r['lignes'][0]['supplements'], ['Salade de fruits'])

    def test_apercu_avant_cloture(self):
        jour = self._mois_passe()
        url = f'{API}/facturation/clotures/apercu/'
        self.assertEqual(self.client_pour(self.gestionnaire).get(url, {'annee': jour.year, 'mois': jour.month})
                         .status_code, 403)
        a = self.client_pour(self.admin).get(url, {'annee': jour.year, 'mois': jour.month}).data
        self.assertTrue(a['cloturable'], a['obstacles'])
        self.assertEqual((a['nb_repas'], a['nb_supplements'], a['nb_employes']), (1, 1, 1))
        self.assertEqual((a['montant_employes'], a['montant_prestataires']), (1000.0, 1200.0))
        self.assertEqual(a['prestataires'][0]['nb_supplements'], 1)
        fact.cloturer_mois(jour.year, jour.month, self.admin)
        a = self.client_pour(self.admin).get(url, {'annee': jour.year, 'mois': jour.month}).data
        self.assertEqual((a['deja_cloture'], a['cloturable']), (True, False))
