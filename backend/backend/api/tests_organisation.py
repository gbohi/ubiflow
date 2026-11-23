"""Tests du lot « Organisation » : N+1, titulaires, réaffectation, arbre, import Excel."""
import io
from datetime import date, datetime, time

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework.test import APITestCase

from . import organisation as org
from .import_collaborateurs import generer_modele
from .models import (
    AffectationHierarchique, AffectationResponsabilite, Agence, Categoriesalarie, Fonction,
    ImportCollaborateurs, Poste, Responsabilite, Service, SituationVehicule, Statut, User, UserAgence,
    UserService,
)

J1, J2, J3 = date(2026, 1, 1), date(2026, 6, 1), date(2026, 9, 1)


def horodate(d):
    return timezone.make_aware(datetime.combine(d, time.min))


class Base:
    def setUp(self):
        self.actif = Statut.objects.get(libelle_statut='Actif')
        self.resp_dept = Responsabilite.objects.get(code='RESP_DEPARTEMENT')
        self.dg = Responsabilite.objects.get(code='DG')
        self.direction = Service.objects.create(libelle_service='Direction générale')
        self.finances = Service.objects.create(libelle_service='Finances', parent=self.direction)
        self.compta = Service.objects.create(libelle_service='Comptabilité', parent=self.finances)

    def creer_user(self, matricule, dept=None, debut=J1, **extra):
        u = User.objects.create_user(matricule, password='Motdepasse1!', nom=matricule.upper(),
                                     prenom='Test', statut=self.actif, **extra)
        if dept:
            UserService.objects.create(user=u, service=dept, date_debut=horodate(debut), statut=self.actif)
        return u

    def nommer_responsable(self, user, dept, debut=J1, fin=None):
        return AffectationResponsabilite.objects.create(user=user, responsabilite=self.resp_dept,
                                                        departement=dept, date_debut=debut, date_fin=fin)


class ResolutionN1Tests(Base, TestCase):
    def setUp(self):
        super().setUp()
        self.dg_user = self.creer_user('dg', self.direction)
        self.daf = self.creer_user('daf', self.finances)
        self.chef = self.creer_user('chef', self.compta)
        self.agent = self.creer_user('agent', self.compta)
        self.nommer_responsable(self.dg_user, self.direction)
        self.nommer_responsable(self.daf, self.finances)
        self.nommer_responsable(self.chef, self.compta)

    def test_automatique_responsable_du_departement(self):
        r = org.n_plus_1(self.agent, J2)
        self.assertEqual(r.responsable, self.chef)
        self.assertEqual(r.source, 'departement')

    def test_responsable_remonte_au_departement_parent(self):
        self.assertEqual(org.n_plus_1(self.chef, J2).responsable, self.daf)
        self.assertEqual(org.n_plus_1(self.chef, J2).source, 'departement_parent')
        self.assertEqual(org.n_plus_1(self.daf, J2).responsable, self.dg_user)

    def test_departement_sans_responsable_remonte(self):
        AffectationResponsabilite.objects.filter(departement=self.compta).update(date_fin=date(2026, 3, 31))
        self.assertEqual(org.n_plus_1(self.agent, J2).responsable, self.daf)
        # Avant la fin de la responsabilité : toujours le chef
        self.assertEqual(org.n_plus_1(self.agent, date(2026, 3, 1)).responsable, self.chef)

    def test_sommet_introuvable(self):
        r = org.n_plus_1(self.dg_user, J2)
        self.assertFalse(r.trouve)
        self.assertEqual(r.source, 'introuvable')

    def test_sans_departement_introuvable(self):
        sans = self.creer_user('sans')
        self.assertFalse(org.n_plus_1(sans, J2).trouve)

    def test_designe_et_historique(self):
        AffectationHierarchique.objects.create(user=self.agent, mode='designe', responsable=self.daf,
                                               date_debut=J2)
        self.assertEqual(org.n_plus_1(self.agent, J3).responsable, self.daf)
        self.assertEqual(org.n_plus_1(self.agent, J3).source, 'designe')
        # Avant la désignation : responsable du département (l'historique n'est pas réécrit)
        self.assertEqual(org.n_plus_1(self.agent, date(2026, 5, 31)).responsable, self.chef)

    def test_designe_inactif_introuvable(self):
        AffectationHierarchique.objects.create(user=self.agent, mode='designe', responsable=self.daf,
                                               date_debut=J1)
        self.daf.is_active = False
        self.daf.save()
        self.assertFalse(org.n_plus_1(self.agent, J2).trouve)

    def test_changement_de_departement(self):
        UserService.objects.filter(user=self.agent).update(date_fin=horodate(date(2026, 5, 31)))
        UserService.objects.create(user=self.agent, service=self.finances, date_debut=horodate(J2),
                                   statut=self.actif)
        self.assertEqual(org.n_plus_1(self.agent, date(2026, 5, 1)).responsable, self.chef)
        self.assertEqual(org.n_plus_1(self.agent, J3).responsable, self.daf)

    def test_n_plus_2(self):
        self.assertEqual(org.n_plus_2(self.agent, J2).responsable, self.daf)

    def test_titulaires_a_une_date(self):
        AffectationResponsabilite.objects.create(user=self.dg_user, responsabilite=self.dg, date_debut=J1,
                                                 date_fin=date(2026, 5, 31))
        AffectationResponsabilite.objects.create(user=self.daf, responsabilite=self.dg, date_debut=J2)
        self.assertEqual(org.titulaires('DG', date(2026, 3, 1)), [self.dg_user])
        self.assertEqual(org.titulaires('DG', J3), [self.daf])
        self.assertEqual(org.titulaires('RESP_DEPARTEMENT', J2, departement=self.compta), [self.chef])
        self.assertEqual(org.titulaires('RESP_DEPARTEMENT', J2), [])  # périmètre requis


class OrganisationApiTests(Base, APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.creer_user('admin1', self.direction)
        self.admin.groups.add(Group.objects.get(name='admin'))
        self.agent = self.creer_user('agent', self.compta)
        self.chef = self.creer_user('chef', self.compta)
        self.client.force_authenticate(self.admin)

    def test_responsable_unique_par_departement(self):
        url = '/api/api/affectations-responsabilite/'
        r = self.client.post(url, {'user': self.chef.pk, 'responsabilite': self.resp_dept.pk,
                                   'departement': self.compta.pk, 'date_debut': '2026-01-01'})
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post(url, {'user': self.agent.pk, 'responsabilite': self.resp_dept.pk,
                                   'departement': self.compta.pk, 'date_debut': '2026-03-01'})
        self.assertEqual(r.status_code, 400)
        # Portée département : le département est obligatoire
        r = self.client.post(url, {'user': self.agent.pk, 'responsabilite': self.resp_dept.pk,
                                   'date_debut': '2026-03-01'})
        self.assertEqual(r.status_code, 400)
        # Portée globale : pas de département
        r = self.client.post(url, {'user': self.agent.pk, 'responsabilite': self.dg.pk,
                                   'departement': self.compta.pk, 'date_debut': '2026-03-01'})
        self.assertEqual(r.status_code, 400)

    def test_responsabilite_systeme_protegee(self):
        self.assertEqual(self.client.delete(f'/api/api/responsabilites/{self.resp_dept.pk}/').status_code, 400)
        r = self.client.patch(f'/api/api/responsabilites/{self.resp_dept.pk}/', {'code': 'AUTRE'})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/api/responsabilites/', {'code': 'resp achats', 'libelle': 'Responsable achats'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['code'], 'RESP_ACHATS')

    def test_affectation_hierarchique_validations(self):
        url = '/api/api/affectations-hierarchiques/'
        r = self.client.post(url, {'user': self.agent.pk, 'mode': 'designe', 'date_debut': '2026-01-01'})
        self.assertEqual(r.status_code, 400)  # responsable manquant
        r = self.client.post(url, {'user': self.agent.pk, 'mode': 'designe', 'responsable': self.agent.pk,
                                   'date_debut': '2026-01-01'})
        self.assertEqual(r.status_code, 400)  # soi-même
        r = self.client.post(url, {'user': self.agent.pk, 'mode': 'designe', 'responsable': self.chef.pk,
                                   'date_debut': '2026-01-01'})
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post(url, {'user': self.agent.pk, 'mode': 'automatique', 'date_debut': '2026-02-01'})
        self.assertEqual(r.status_code, 400)  # chevauchement

    def test_reaffectation_exceptionnelle(self):
        AffectationHierarchique.objects.create(user=self.agent, mode='automatique', date_debut=J1)
        url = f'/api/api/collaborateurs/{self.agent.pk}/reaffecter-n-plus-1/'
        r = self.client.post(url, {'mode': 'designe', 'responsable': self.chef.pk, 'date_effet': '2026-06-01',
                                   'motif': ''})
        self.assertEqual(r.status_code, 400)  # motif obligatoire
        r = self.client.post(url, {'mode': 'designe', 'responsable': self.chef.pk, 'date_effet': '2026-06-01',
                                   'motif': 'Intérim du chef de service'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['n_plus_1']['personne']['id'], self.chef.pk)
        self.assertTrue(r.data['n_plus_1']['exceptionnelle'])
        ancienne = AffectationHierarchique.objects.get(user=self.agent, mode='automatique')
        self.assertEqual(ancienne.date_fin, date(2026, 5, 31))
        # Réservé aux administrateurs
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_n1_designe_non_supprimable(self):
        AffectationHierarchique.objects.create(user=self.agent, mode='designe', responsable=self.chef,
                                               date_debut=J1)
        self.assertEqual(self.client.delete(f'/api/api/users/{self.chef.pk}/').status_code, 400)
        self.assertTrue(User.objects.filter(pk=self.chef.pk).exists())

    def test_organisation_du_collaborateur(self):
        self.nommer_responsable(self.chef, self.compta)
        SituationVehicule.objects.create(user=self.agent, possede_vehicule=True, date_debut=J1)
        r = self.client.get(f'/api/api/collaborateurs/{self.agent.pk}/organisation/?date=2026-06-01')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['departement']['libelle'], 'Comptabilité')
        self.assertEqual(r.data['n_plus_1']['personne']['id'], self.chef.pk)
        self.assertTrue(r.data['possede_vehicule'])
        # Un employé voit sa propre situation, pas celle des autres
        self.client.force_authenticate(self.agent)
        self.assertEqual(self.client.get('/api/api/collaborateurs/moi/organisation/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/api/collaborateurs/{self.chef.pk}/organisation/').status_code, 403)

    def test_arbre_et_cycle_refuse(self):
        self.nommer_responsable(self.chef, self.compta)
        r = self.client.get('/api/api/departements/arbre/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]['libelle'], 'Direction générale')
        self.assertEqual(r.data[0]['enfants'][0]['enfants'][0]['responsable']['id'], self.chef.pk)
        r = self.client.patch(f'/api/api/services/{self.direction.pk}/', {'parent': self.compta.pk})
        self.assertEqual(r.status_code, 400)
        r = self.client.get(f'/api/api/services/{self.compta.pk}/')
        self.assertEqual(r.data['chemin'], 'Direction générale › Finances › Comptabilité')


class ImportCollaborateursTests(Base, APITestCase):
    URL = '/api/api/imports-collaborateurs/'

    def setUp(self):
        super().setUp()
        self.admin = self.creer_user('admin1')
        self.admin.groups.add(Group.objects.get(name='admin'))
        self.client.force_authenticate(self.admin)
        self.abidjan = Agence.objects.create(nom_agence='Abidjan', code='ABJ')
        self.cadre = Categoriesalarie.objects.create(libelle='Cadre')
        Poste.objects.create(libelle='Comptable', service=self.compta, fonction=Fonction.objects.create(libelle='Compta'))

    def fichier(self, lignes, entetes=None):
        wb = Workbook()
        ws = wb.active
        ws.append(entetes or ['Matricule', 'Nom', 'Prénoms', 'Agence', 'Département', 'Poste', 'Catégorie',
                              'Véhicule personnel', 'Matricule N+1'])
        for ligne in lignes:
            ws.append(ligne)
        sortie = io.BytesIO()
        wb.save(sortie)
        return SimpleUploadedFile('collaborateurs.xlsx', sortie.getvalue())

    def envoyer(self, lignes, simulation=False, date_effet='2026-01-01', **kw):
        return self.client.post(self.URL, {'fichier': self.fichier(lignes, **kw), 'date_effet': date_effet,
                                           'simulation': 'true' if simulation else 'false'}, format='multipart')

    LIGNES = [
        ['A1', 'KONE', 'Fatou', 'ABJ', 'Comptabilité', 'Comptable', 'cadre', 'oui', 'B2'],
        ['B2', 'TRAORE', 'Moussa', 'Abidjan', 'Finances', '', '', 'NON', 'AUTO'],
        ['C3', 'YAO', 'Ange', 'Bouaké', 'Finances', '', '', '', ''],
    ]

    def test_simulation_ne_modifie_rien(self):
        r = self.envoyer(self.LIGNES, simulation=True)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['nb_crees'], r.data['nb_rejetes']), (2, 1))
        self.assertFalse(User.objects.filter(username='A1').exists())
        self.assertTrue(ImportCollaborateurs.objects.get().simulation)

    def test_import_reel(self):
        r = self.envoyer(self.LIGNES)
        self.assertEqual(r.status_code, 201, r.data)
        rapport = {e['matricule']: e for e in r.data['rapport']}
        self.assertEqual(rapport['A1']['resultat'], 'cree')
        self.assertEqual(rapport['C3']['resultat'], 'rejete')
        self.assertIn('Agence inconnu(e)', rapport['C3']['messages'][0])
        a1 = User.objects.get(username='A1')
        self.assertFalse(a1.has_usable_password())
        self.assertTrue(a1.groups.filter(name='employe').exists())
        self.assertEqual(org.departement_de(a1, J2), self.compta)
        self.assertTrue(org.possede_vehicule(a1, J2))
        # N+1 désigné vers un collaborateur créé plus bas dans le fichier
        self.assertEqual(org.n_plus_1(a1, J2).responsable.username, 'B2')
        self.assertEqual(org.organisation_de(a1, J2)['categorie']['libelle'], 'Cadre')

    def test_mise_a_jour_historise(self):
        self.envoyer(self.LIGNES)
        a1 = User.objects.get(username='A1')
        r = self.envoyer([['A1', 'KONE', 'Fatou', '', 'Finances', '', '', '', '']], date_effet='2026-06-01')
        self.assertEqual(r.data['rapport'][0]['resultat'], 'mis_a_jour')
        self.assertEqual(org.departement_de(a1, date(2026, 5, 31)), self.compta)
        self.assertEqual(org.departement_de(a1, J2), self.finances)
        # Cellule vide = pas de changement (agence conservée)
        self.assertEqual(org.valeur_en_cours(a1, 'agence', J2), self.abidjan)
        self.assertEqual(UserAgence.objects.filter(user=a1).count(), 1)
        # Même fichier une 2e fois : rien ne change
        r = self.envoyer([['A1', 'KONE', 'Fatou', '', 'Finances', '', '', '', '']], date_effet='2026-06-01')
        self.assertEqual(r.data['rapport'][0]['resultat'], 'inchange')

    def test_entetes_obligatoires_et_droits(self):
        r = self.envoyer([['A1']], entetes=['Matricule'])
        self.assertEqual(r.status_code, 400)
        r = self.envoyer([['A1', 'X', 'Y'], ['a1', 'X', 'Y']], entetes=['Matricule', 'Nom', 'Prénoms'])
        self.assertEqual(r.data['nb_rejetes'], 1)  # matricule en double
        self.client.force_authenticate(self.creer_user('simple'))
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_modele_relisible(self):
        r = self.client.get(self.URL + 'modele/')
        self.assertEqual(r.status_code, 200)
        wb = load_workbook(io.BytesIO(b''.join(r.streaming_content) if r.streaming else r.content))
        self.assertIn('Instructions', wb.sheetnames)
        self.assertEqual(wb['Collaborateurs'].cell(1, 1).value, 'Matricule *')
        self.assertTrue(generer_modele())
