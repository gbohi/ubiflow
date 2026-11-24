"""
Lot 3 : calcul des missions (§7), figement des barèmes, barèmes datés,
devises. Réutilise l'organisation de test du lot 2 (workflow.tests.Base).
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from api.models import AffectationResponsabilite, Categoriesalarie, Responsabilite, SituationVehicule, UserCategoriesalarie
from baremes.models import PerDiem, TarifKilometrique, TarifTransportVille, TauxChange
from demandes.models import Demande, TypeDemande
from workflow import conditions
from workflow.tests import J0, Base, h

from . import calcul
from .models import Distance, LigneCalcul, Ville

MISSION = {'motif': 'Audit agence de Bouaké', 'depart_le': '2026-12-01T08:00:00', 'retour_le': '2026-12-04T18:00:00',
           'moyen_transport': 'transport_commun', 'trajet': 'aller_retour',
           'frais': [{'rubrique': 'hebergement', 'montant': '60000', 'devise': 'XOF', 'description': '3 nuits'}]}


class MissionBase(Base):
    def setUp(self):
        super().setUp()
        self.mlo = TypeDemande.objects.get(code='MLO')
        self.mhp = TypeDemande.objects.get(code='MHP')
        self.cadre = Categoriesalarie.objects.get(libelle='Cadre')
        UserCategoriesalarie.objects.create(user=self.agent, categoriesalarie=self.cadre, date_debut=h(J0),
                                            statut=self.actif)
        self.comptable = self.user('cpt', self.compta)
        AffectationResponsabilite.objects.create(
            user=self.comptable, responsabilite=Responsabilite.objects.get(code='CHEF_COMPTABLE'), date_debut=J0)
        self.abidjan = Ville.objects.get(libelle='Abidjan')
        self.bouake = Ville.objects.get(libelle='Bouaké')
        self.paris = Ville.objects.get(libelle='Paris')
        TarifTransportVille.objects.create(ville=self.bouake, montant=30000, devise='XOF', date_effet=J0, motif='x')

    def mission(self, **autres):
        return {**MISSION, 'ville_depart': self.abidjan.pk, 'ville_destination': self.bouake.pk, **autres}

    def creer_mission(self, type_demande=None, user=None, **autres):
        self.en(user or self.agent)
        r = self.client.post('/api/api/demandes/', {'type_demande': (type_demande or self.mlo).pk,
                                                    'objet': 'Mission Bouaké', 'mission': self.mission(**autres)},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']


class CalculTests(MissionBase):
    def calculer(self, type_mission='locale', possede_vehicule=False, **autres):
        donnees = calcul.normaliser(type_mission, self.mission(**autres), complet=True)
        fig = calcul.figer_baremes(type_mission, self.cadre, donnees, possede_vehicule, timezone.localdate())
        return calcul.calculer(type_mission, donnees, fig)

    def test_nombre_de_jours(self):
        d = timezone.make_aware(timezone.datetime(2026, 12, 1, 8))
        self.assertEqual(calcul.nombre_jours(d, d + timedelta(hours=10)), 1)
        self.assertEqual(calcul.nombre_jours(d, d + timedelta(days=3)), 4)

    def test_retour_avant_depart_refuse(self):
        with self.assertRaises(Exception) as e:
            calcul.normaliser('locale', self.mission(retour_le='2026-11-30T10:00:00'), complet=True)
        self.assertIn('retour_le', str(e.exception.detail))

    def test_exemple_du_cahier(self):
        """§7.6 : 4 jours × 25 000 + transport ville 30 000 + hébergement 60 000 = 190 000."""
        r = self.calculer()
        self.assertEqual(r['erreurs'], [])
        self.assertEqual([l['montant_ref'] for l in r['lignes']], ['100000.00', '30000.00', '60000.00'])
        self.assertEqual(r['total_ref'], '190000.00')
        self.assertIn('4 jour(s)', r['lignes'][0]['libelle'])

    def test_vehicule_personnel(self):
        Distance.objects.create(ville_a=self.bouake, ville_b=self.abidjan, km=350)
        TarifKilometrique.objects.create(montant=100, devise='XOF', date_effet=J0, motif='x')
        r = self.calculer(possede_vehicule=True, moyen_transport='vehicule_personnel')
        transport = r['lignes'][1]
        self.assertEqual((transport['base'], transport['montant_ref']), ('700', '70000.00'))
        # sans véhicule déclaré : refusé
        r = self.calculer(possede_vehicule=False, moyen_transport='vehicule_personnel')
        self.assertTrue(any('véhicule' in e for e in r['erreurs']))
        # autre distance : justification obligatoire, écart signalé
        r = self.calculer(possede_vehicule=True, moyen_transport='vehicule_personnel', distance_km=400)
        self.assertTrue(any('Justifiez' in e for e in r['erreurs']))
        r = self.calculer(possede_vehicule=True, moyen_transport='vehicule_personnel', distance_km=400,
                          justification_distance='Route de Tiébissou fermée')
        self.assertEqual(r['lignes'][1]['montant_ref'], '80000.00')
        self.assertIn('400 km au lieu de 350', r['signalements'][0])

    def test_vehicule_de_service_sans_indemnite(self):
        r = self.calculer(moyen_transport='vehicule_service')
        self.assertEqual(r['lignes'][1]['montant_ref'], '0.00')

    def test_ville_sans_tarif(self):
        man = Ville.objects.get(libelle='Man')
        r = self.calculer(ville_destination=man.pk)
        self.assertTrue(any('Aucun tarif' in e for e in r['erreurs']))
        r = self.calculer(ville_destination=man.pk, montant_transport_manuel='45000',
                          justification_transport='Car UTB, aller-retour')
        self.assertEqual(r['erreurs'], [])
        self.assertIn('Ville sans tarif', r['signalements'][0])

    def test_hors_pays_forfait_et_devises(self):
        PerDiem.objects.create(type_mission='hors_pays', categorie=self.cadre, montant=150, devise='EUR',
                               date_effet=J0, motif='x')
        frais = [{'rubrique': 'visa', 'montant': '99', 'devise': 'EUR'},
                 {'rubrique': 'aerien', 'montant': '450000', 'devise': 'XOF'}]
        r = self.calculer('hors_pays', ville_destination=self.paris.pk, frais=frais)
        self.assertEqual(r['erreurs'], [])
        par_rubrique = {l['rubrique']: l for l in r['lignes']}
        self.assertEqual(par_rubrique['per_diem']['montant'], '600.00')          # 4 × 150 EUR
        self.assertEqual(par_rubrique['per_diem']['montant_ref'], '393574.20')   # × 655,957
        self.assertEqual(par_rubrique['transport']['montant_ref'], '20000.00')   # forfait aéroport
        self.assertEqual(par_rubrique['visa']['montant_ref'], '64939.74')
        # forfait ajusté : justification obligatoire et écart signalé
        r = self.calculer('hors_pays', ville_destination=self.paris.pk, forfait_transport='35000')
        self.assertTrue(any('Justifiez' in e for e in r['erreurs']))
        r = self.calculer('hors_pays', ville_destination=self.paris.pk, forfait_transport='35000',
                          justification_forfait='Départ de Yamoussoukro')
        self.assertIn('35 000 XOF au lieu de 20 000', r['signalements'][0])

    def test_bareme_ou_taux_manquant(self):
        r = self.calculer('hors_pays', ville_destination=self.paris.pk,
                          frais=[{'rubrique': 'visa', 'montant': '100', 'devise': 'USD'}])
        self.assertTrue(any('per diem' in e for e in r['erreurs']))
        self.assertTrue(any('USD' in e for e in r['erreurs']))

    def test_rubrique_non_prevue(self):
        with self.assertRaises(Exception):
            calcul.normaliser('locale', self.mission(frais=[{'rubrique': 'visa', 'montant': '10'}]), complet=True)


class SoumissionMissionTests(MissionBase):
    def test_soumission_calcule_et_fige(self):
        pk = self.creer_mission()
        d = self.soumettre(pk)
        annee = timezone.localdate().year
        self.assertEqual(d['reference'], f'MLO-{annee}-00001')
        self.assertEqual(Decimal(d['montant_demande']), Decimal('190000'))
        self.assertEqual(d['calcul']['total_ref'], '190000.00')
        self.assertEqual(d['mission']['nombre_jours'], 4)
        demande = Demande.objects.get(pk=pk)
        self.assertEqual(LigneCalcul.objects.filter(version_contenu=demande.version_courante).count(), 3)
        plan = [e['code'] for e in demande.instances.get().plan if e['statut'] != 'sautee']
        self.assertEqual(plan, ['n_plus_1', 'dg', 'daf', 'chef_comptable'])

    def test_montant_saisi_ignore(self):
        self.en(self.agent)
        r = self.client.post('/api/api/demandes/', {'type_demande': self.mlo.pk, 'objet': 'x', 'montant_demande': '1',
                                                    'mission': self.mission()}, format='json')
        self.assertIsNone(r.data['montant_demande'])

    def test_soumission_refusee_si_bareme_manquant(self):
        pk = self.creer_mission(type_demande=self.mhp, ville_destination=self.paris.pk)
        d = self.soumettre(pk, attendu=400)
        self.assertIn('calcul', d)

    def test_soumission_incomplete(self):
        self.en(self.agent)
        r = self.client.post('/api/api/demandes/', {'type_demande': self.mlo.pk, 'objet': 'x',
                                                    'mission': {'motif': 'x'}}, format='json')
        d = self.soumettre(r.data['id'], attendu=400)
        self.assertIn('ville_destination', d['mission'])

    def test_changement_de_bareme_sans_effet_sur_les_demandes_existantes(self):
        pk = self.creer_mission()
        self.soumettre(pk)
        PerDiem.objects.create(type_mission='locale', categorie=self.cadre, montant=40000, devise='XOF',
                               date_effet=timezone.localdate(), motif='Revalorisation')
        self.en(self.agent)
        detail = self.client.get(f'/api/api/demandes/{pk}/').data
        self.assertEqual(detail['calcul']['total_ref'], '190000.00')
        # retour pour correction sans changement déterminant : barèmes du cycle 1 conservés
        self.agir(pk, self.chef, 'retourner', motif='Préciser le motif')
        self.en(self.agent).client.patch(f'/api/api/demandes/{pk}/', {'mission': self.mission(motif='Audit annuel')},
                                         format='json')
        apercu = self.client.post('/api/api/missions/calculer/', {'type_demande': self.mlo.pk, 'demande': pk,
                                                                  'mission': self.mission()}, format='json').data
        self.assertEqual(apercu['total_ref'], '190000.00')
        d = self.soumettre(pk)
        self.assertEqual(d['calcul']['total_ref'], '190000.00')
        # nouveau retour, dates modifiées : recalcul aux barèmes du jour, noté dans l'historique
        self.agir(pk, self.chef, 'retourner', motif='Dates')
        self.en(self.agent).client.patch(
            f'/api/api/demandes/{pk}/', {'mission': self.mission(retour_le='2026-12-03T18:00:00')}, format='json')
        d = self.soumettre(pk)
        self.assertEqual(d['calcul']['total_ref'], '210000.00')  # 3 × 40 000 + 30 000 + 60 000
        self.assertEqual(d['calcul']['recalcul']['ancien_total_ref'], '190000.00')
        self.assertIn('barèmes du', Demande.objects.get(pk=pk).actions.filter(type='resoumission').last().motif)

    def test_conditions_sur_la_mission(self):
        codes = [c['code'] for c in conditions.champs_disponibles(self.mlo)]
        self.assertIn('mission.nombre_jours', codes)
        pk = self.creer_mission()
        self.soumettre(pk)
        from demandes.services import contexte_conditions
        ctx = contexte_conditions(Demande.objects.get(pk=pk))
        self.assertEqual((ctx['mission.nombre_jours'], ctx['mission.pays_destination']), (4, 'CI'))

    def test_vehicule_personnel_selon_situation(self):
        Distance.objects.create(ville_a=self.abidjan, ville_b=self.bouake, km=350)
        TarifKilometrique.objects.create(montant=100, devise='XOF', date_effet=J0, motif='x')
        pk = self.creer_mission(moyen_transport='vehicule_personnel')
        self.assertIn('calcul', self.soumettre(pk, attendu=400))
        SituationVehicule.objects.create(user=self.agent, possede_vehicule=True, date_debut=J0)
        d = self.soumettre(pk)
        self.assertEqual(d['calcul']['total_ref'], '230000.00')

    def test_duplication(self):
        pk = self.creer_mission()
        self.soumettre(pk)
        self.en(self.agent)
        r = self.client.post(f'/api/api/demandes/{pk}/dupliquer/')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['mission']['ville_destination'], self.bouake.pk)


class DevisesTests(MissionBase):
    def test_demande_simple_en_devise(self):
        pk = self.creer(montant='1000')
        Demande.objects.filter(pk=pk).update(devise='EUR')
        self.soumettre(pk)
        demande = Demande.objects.get(pk=pk)
        self.assertEqual(demande.montant_demande_ref, Decimal('655957.00'))
        self.assertEqual(demande.parametres_figes['taux']['EUR']['taux'], '655.957000')
        # le taux reste figé même si le barème change
        TauxChange.objects.create(devise='EUR', taux=Decimal('700'), date_effet=timezone.localdate(), motif='x')
        self.agir(pk, self.chef, 'retourner', motif='x')
        self.soumettre(pk)
        self.assertEqual(Demande.objects.get(pk=pk).montant_demande_ref, Decimal('655957.00'))

    def test_devise_sans_taux(self):
        pk = self.creer(montant='1000')
        Demande.objects.filter(pk=pk).update(devise='USD')
        self.assertIn('devise', self.soumettre(pk, attendu=400))


class BaremesApiTests(MissionBase):
    URL = '/api/api/baremes/per-diem/'

    def ligne(self, user, attendu=201, **data):
        self.en(user)
        r = self.client.post(self.URL, {'type_mission': 'locale', 'categorie': self.cadre.pk, 'montant': '30000',
                                        'devise': 'xof', 'motif': 'Revalorisation', **data}, format='json')
        self.assertEqual(r.status_code, attendu, r.data)
        return r.data

    def test_droits(self):
        self.ligne(self.agent, attendu=403, date_effet='2027-01-01')
        self.en(self.agent)
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        finances = self.user('fin', groupes=('admin_finances',))
        d = self.ligne(finances, date_effet='2027-01-01')
        self.assertEqual(d['devise'], 'XOF')
        self.assertEqual(d['precedente']['valeur'], '25000.00')
        self.assertFalse(d['en_vigueur'])

    def test_aucune_modification_suppression_si_future(self):
        finances = self.user('fin', groupes=('admin_finances',))
        future = self.ligne(finances, date_effet='2027-01-01')
        self.assertEqual(self.client.patch(f"{self.URL}{future['id']}/", {'montant': 1}, format='json').status_code, 405)
        self.ligne(finances, attendu=400, date_effet='2027-01-01')  # même date d'effet
        self.ligne(finances, attendu=400, date_effet='2027-02-01', motif='')
        en_vigueur = PerDiem.objects.get(categorie=self.cadre, type_mission='locale', date_effet=J0)
        self.assertEqual(self.client.delete(f'{self.URL}{en_vigueur.pk}/').status_code, 400)
        self.assertEqual(self.client.delete(f"{self.URL}{future['id']}/").status_code, 204)

    def test_devise_de_reference(self):
        finances = self.user('fin', groupes=('admin_finances',))
        self.en(finances)
        r = self.client.get('/api/api/parametres-systeme/')
        self.assertEqual((r.data['devise_reference'], r.data['modifiable_devise']), ('XOF', True))
        self.soumettre(self.creer())
        self.en(finances)
        r = self.client.patch('/api/api/parametres-systeme/', {'devise_reference': 'EUR'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/api/baremes/taux-change/', {'devise': 'XOF', 'taux': '1', 'date_effet': '2027-01-01',
                                                               'motif': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_lieux(self):
        self.en(self.agent)
        villes = self.client.get('/api/api/villes/?pays_code=CI').data
        self.assertTrue(any(v['libelle'] == 'Abidjan' for v in villes))
        self.assertEqual(self.client.post('/api/api/villes/', {'libelle': 'Tiassalé', 'pays': self.abidjan.pays_id},
                                          format='json').status_code, 403)
        admin = self.user('adm', groupes=('admin',))
        self.en(admin)
        r = self.client.post('/api/api/distances/', {'ville_a': self.bouake.pk, 'ville_b': self.abidjan.pk, 'km': 350},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post('/api/api/distances/', {'ville_a': self.abidjan.pk, 'ville_b': self.bouake.pk, 'km': 340},
                             format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.get(f'/api/api/distances/entre/?a={self.abidjan.pk}&b={self.bouake.pk}')
        self.assertEqual(r.data['km'], 350)


class FiltreParTypeTests(MissionBase):
    def test_filtre_des_listes_par_type(self):
        self.soumettre(self.creer_mission())
        self.soumettre(self.creer())  # FRC
        self.en(self.agent)
        r = self.client.get(f'/api/api/demandes/?type_demande={self.mlo.pk}').data['results']
        self.assertEqual([(d['type_code'], d['type_icone']) for d in r], [('MLO', 'ri-road-map-line')])
        self.en(self.chef)  # N+1 des deux demandes
        self.assertEqual(self.client.get('/api/api/taches/').data['count'], 2)
        r = self.client.get(f'/api/api/taches/?type_demande={self.frc.pk}').data['results']
        self.assertEqual([t['demande']['type_code'] for t in r], ['FRC'])

    def test_filtre_par_dates(self):
        brouillon = self.creer_mission()
        self.soumettre(self.creer())
        jour = timezone.localdate()
        self.en(self.agent)
        r = self.client.get(f'/api/api/demandes/?du={jour}&au={jour}').data
        self.assertEqual(r['count'], 2)  # le brouillon compte à sa date de création
        r = self.client.get(f'/api/api/demandes/?du={jour + timedelta(days=1)}').data
        self.assertEqual(r['count'], 0)
        self.assertEqual(self.client.get('/api/api/demandes/?du=31-12-2026').status_code, 400)
        Demande.objects.filter(pk=brouillon).update(created_at=timezone.now() - timedelta(days=10))
        r = self.client.get(f'/api/api/demandes/?au={jour - timedelta(days=5)}').data
        self.assertEqual([d['id'] for d in r['results']], [brouillon])
        self.en(self.chef)
        self.assertEqual(self.client.get(f'/api/api/taches/?du={jour}').data['count'], 1)
        self.assertEqual(self.client.get(f'/api/api/taches/?au={jour - timedelta(days=1)}').data['count'], 0)
