"""Tests du socle : authentification, utilisateurs, rôles et paramètres."""
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Agence, Categoriesalarie, Fonction, Poste, Service, Statut, User, UserAgence


class SocleTests(APITestCase):
    def setUp(self):
        self.actif = Statut.objects.get(libelle_statut='Actif')
        self.admin = User.objects.create_user('admin1', password='Motdepasse1!', nom='A', prenom='B',
                                              statut=self.actif)
        self.admin.groups.add(Group.objects.get(name='admin'))
        self.employe = User.objects.create_user('emp1', password='Motdepasse1!', nom='E', prenom='F',
                                                statut=self.actif)
        self.employe.groups.add(Group.objects.get(name='employe'))

    def connecter(self, user):
        self.client.force_authenticate(user)

    def test_connexion_jwt(self):
        r = self.client.post('/api/api/token/', {'username': 'emp1', 'password': 'Motdepasse1!'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)

    def test_parametres_crud_admin(self):
        self.connecter(self.admin)
        for url, champ in [('agences', 'nom_agence'), ('services', 'libelle_service'),
                           ('fonctions', 'libelle'), ('categoriesalaries', 'libelle')]:
            r = self.client.post(f'/api/api/{url}/', {champ: 'Test'})
            self.assertEqual(r.status_code, 201, (url, r.data))
            # Libellé en double refusé
            r = self.client.post(f'/api/api/{url}/', {champ: 'test'})
            self.assertEqual(r.status_code, 400, url)

    def test_employe_lecture_seule(self):
        self.connecter(self.employe)
        self.assertEqual(self.client.get('/api/api/agences/').status_code, 200)
        self.assertEqual(self.client.post('/api/api/agences/', {'nom_agence': 'X'}).status_code, 403)
        self.assertEqual(self.client.get('/api/api/users/').status_code, 403)

    def test_poste_et_suppression_protegee(self):
        self.connecter(self.admin)
        service = Service.objects.create(libelle_service='Finances')
        fonction = Fonction.objects.create(libelle='Comptable')
        r = self.client.post('/api/api/postes/', {'libelle': 'Comptable senior', 'service': service.id,
                                                  'fonction': fonction.id})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['service_libelle'], 'Finances')
        # Un département utilisé par un poste ne peut pas être supprimé
        self.assertEqual(self.client.delete(f'/api/api/services/{service.id}/').status_code, 400)

    def test_creation_utilisateur_et_affectations(self):
        self.connecter(self.admin)
        r = self.client.post('/api/api/users/register/', {
            'username': 'nouveau', 'nom': 'N', 'prenom': 'P', 'statut': self.actif.id,
            'password': 'Motdepasse1!', 'password2': 'Motdepasse1!',
            'groups': [Group.objects.get(name='employe').id],
        })
        self.assertEqual(r.status_code, 201, r.data)
        user = User.objects.get(username='nouveau')
        agence = Agence.objects.create(nom_agence='Abidjan')
        r = self.client.post('/api/api/user-agences/', {'user': user.id, 'agence': agence.id,
                                                        'date_debut': timezone.now(), 'statut': self.actif.id})
        self.assertEqual(r.status_code, 201, r.data)
        # Deux agences en même temps : refusé
        r = self.client.post('/api/api/user-agences/', {'user': user.id, 'agence': agence.id,
                                                        'date_debut': timezone.now(), 'statut': self.actif.id})
        self.assertEqual(r.status_code, 400)
        r = self.client.get(f'/api/api/users/{user.id}/')
        self.assertEqual(r.data['derniere_agence']['agence_nom'], 'Abidjan')
        self.assertEqual(r.data['roles'], ['employe'])

    def test_me(self):
        self.connecter(self.employe)
        r = self.client.get('/api/api/users/me/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['username'], 'emp1')

    def test_roles_systeme_proteges(self):
        self.connecter(self.admin)
        g = Group.objects.get(name='employe')
        self.assertEqual(self.client.delete(f'/api/api/groups/{g.id}/').status_code, 403)


class LimiteDemandesCodeTests(APITestCase):
    """Mot de passe oublié : 3 demandes de code par matricule sur 30 minutes."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()  # compteurs (limite par matricule et par adresse IP) remis à zéro
        self.url = '/api/api/users/forgot-password/'

    def demander(self, matricule):
        return self.client.post(self.url, {'username': matricule}, format='json')

    def test_quatrieme_demande_refusee_avec_le_delai(self):
        actif = Statut.objects.get(libelle_statut='Actif')
        User.objects.create_user('otp1', password='Motdepasse1!', nom='O', prenom='T', statut=actif)
        for _ in range(3):
            self.assertEqual(self.demander('otp1').status_code, 200)
        r = self.demander('otp1')
        self.assertEqual(r.status_code, 429)
        self.assertIn('Veuillez réessayer dans 30 minutes', r.data['error'])
        self.assertEqual(r.data['reessayer_dans_minutes'], 30)

    def test_matricule_inconnu_meme_regle_et_compteurs_distincts(self):
        for _ in range(3):
            self.assertEqual(self.demander('inconnu').status_code, 200)
        self.assertEqual(self.demander('inconnu').status_code, 429)  # rien ne révèle si le compte existe
        self.assertEqual(self.demander('autre').status_code, 200)    # chaque matricule a son compteur

    def test_limite_par_adresse_en_francais(self):
        # Au-delà de 10 appels par heure depuis la même adresse : message en français avec le délai
        for i in range(10):
            self.demander(f'm{i}')
        r = self.demander('m99')
        self.assertEqual(r.status_code, 429)
        self.assertTrue(r.data['detail'].startswith('Trop de tentatives. Veuillez réessayer dans'))
