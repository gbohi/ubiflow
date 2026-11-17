"""
Comptes des agents de comptoir créés par le responsable du prestataire,
agences d'intervention (restriction du comptoir) et historique des retraits.

Lancer : python manage.py test api.tests_equipe_comptoir
"""
from datetime import timedelta

from django.utils import timezone

from .models import Agence, AgencePrestataire, Commande, Retrait, User
from .tests import API, _EspacePrestataireBase

NOUVEAU = 'Comptoir#2026'


class EquipeComptoirTests(_EspacePrestataireBase):

    def setUp(self):
        super().setUp()
        # A dessert aussi Yopougon ; Vridi n'est desservie par personne
        AgencePrestataire.objects.create(prestataire=self.presta_a, agence=self.yop, statut=self.statut,
                                         date_debut=timezone.now() - timedelta(days=400))
        self.vridi = Agence.objects.create(nom_agence='Vridi')

    def creer(self, **extra):
        donnees = {'nom': 'Diallo', 'prenom': 'Seydou', 'username': 'sdiallo', 'password': NOUVEAU,
                   'password2': NOUVEAU, 'agences': [self.agence.id], **extra}
        return self.client_pour(self.resp_a).post(f'{API}/prestataire/equipe/', donnees, format='json')

    def test_creation_et_restriction_aux_agences(self):
        r = self.creer()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual([a['nom'] for a in r.data['agences']], [self.agence.nom_agence])
        agent = User.objects.get(username='sdiallo')
        self.assertEqual(agent.prestataire_id, self.presta_a.id)
        self.assertTrue(agent.groups.filter(name='agent_comptoir').exists())
        self.assertTrue(agent.check_password(NOUVEAU))
        c = self.client_pour(agent)
        ctx = c.get(f'{API}/prestataire/contexte/').data
        self.assertEqual([a['id'] for a in ctx['agences']], [self.agence.id])
        self.assertEqual(c.get(f'{API}/prestataire/liste-du-jour/', {'agence': self.yop.id}).status_code, 403)
        self.assertEqual(c.get(f'{API}/prestataire/comptoir/service/', {'agence': self.yop.id}).status_code, 403)
        menu = self.menu_du_jour(agence=self.yop, plats=[self.plat_b])
        Commande.objects.create(user=self.emp_yop, menu=menu, plat=self.plat_b)
        v = c.post(f'{API}/prestataire/comptoir/valider/',
                   {'menu_id': menu.id, 'user_id': self.emp_yop.id, 'mode': 'saisie'}, format='json')
        self.assertEqual(v.status_code, 403)
        # Agent sans agence cochée (créé par UbiPharm avant) : toutes les agences
        ctx = self.client_pour(self.agent_a).get(f'{API}/prestataire/contexte/').data
        self.assertEqual({a['id'] for a in ctx['agences']}, {self.agence.id, self.yop.id})

    def test_validations(self):
        self.assertEqual(self.creer(agences=[]).status_code, 400)
        self.assertEqual(self.creer(agences=[self.vridi.id]).status_code, 400)
        self.assertEqual(self.creer(password2='Autre#2026').status_code, 400)
        self.assertEqual(self.creer(password='faible', password2='faible').status_code, 400)
        self.assertEqual(self.creer(username='agenta').status_code, 400)
        self.assertEqual(self.client_pour(self.agent_a).get(f'{API}/prestataire/equipe/').status_code, 403)

    def test_modifier_desactiver_mot_de_passe(self):
        aid = self.creer().data['id']
        c = self.client_pour(self.resp_a)
        r = c.patch(f'{API}/prestataire/equipe/{aid}/', {'agences': [self.agence.id, self.yop.id],
                                                         'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['agences']), 2)
        self.assertFalse(r.data['is_active'])
        r = c.post(f'{API}/prestataire/equipe/{aid}/mot-de-passe/', {'password': 'Neuf#2026x',
                                                                     'password2': 'Neuf#2026x'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(User.objects.get(pk=aid).check_password('Neuf#2026x'))
        # Pas les responsables, pas les comptes d'un autre prestataire
        self.assertEqual(c.patch(f'{API}/prestataire/equipe/{self.resp_a.id}/', {'nom': 'X'},
                                 format='json').status_code, 403)
        self.assertEqual(c.patch(f'{API}/prestataire/equipe/{self.resp_b.id}/', {'nom': 'X'},
                                 format='json').status_code, 404)

    def test_ubipharm_choisit_les_agences(self):
        r = self.client_pour(self.admin).patch(f'{API}/users/{self.agent_a.id}/',
                                               {'agences_comptoir': [self.yop.id]}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(list(self.agent_a.agences_comptoir.values_list('id', flat=True)), [self.yop.id])
        r = self.client_pour(self.admin).patch(f'{API}/users/{self.agent_a.id}/',
                                               {'agences_comptoir': [self.vridi.id]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_historique_des_retraits(self):
        hier = timezone.now() - timedelta(days=1)
        for emp, agence, plat, quand in ((self.employe, self.agence, self.plat_a, hier),
                                        (self.emp_yop, self.yop, self.plat_b, timezone.now())):
            menu = self.menu_du_jour(agence=agence, plats=[plat])
            Commande.objects.create(user=emp, menu=menu, plat=plat, statut='retiree')
            Retrait.objects.create(user=emp, menu=menu, badge_matricule=emp.username, valide_par=self.agent_a,
                                   mode='badge', date_retrait=quand)
        url = f'{API}/prestataire/comptoir/historique/'
        r = self.client_pour(self.resp_a).get(url).data
        self.assertEqual(r['total'], 2 if hier.date().month == timezone.localdate().month else 1)
        debut = (timezone.localdate() - timedelta(days=3)).isoformat()
        r = self.client_pour(self.resp_a).get(url, {'debut': debut, 'search': 'Placali'}).data
        self.assertEqual([x['matricule'] for x in r['resultats']], ['empyop'])
        self.assertEqual(r['resultats'][0]['plats'][0]['plat'], 'Placali')
        r = self.client_pour(self.agent_a).get(url, {'debut': debut, 'valide_par': 'moi'}).data
        self.assertEqual((r['total'], r['kpis']['par_badge']), (2, 2))
        # Agent limité au Siège : ne voit pas Yopougon
        self.agent_a2.agences_comptoir.set([self.agence])
        r = self.client_pour(self.agent_a2).get(url, {'debut': debut}).data
        self.assertEqual([x['agence'] for x in r['resultats']], [self.agence.nom_agence])
        self.assertEqual(self.client_pour(self.employe).get(url).status_code, 403)

    def test_historique_non_retires(self):
        avant_hier = self.menu_du_jour(plats=[self.plat_a], jours=-2)
        oubli = Commande.objects.create(user=self.employe, menu=avant_hier, plat=self.plat_a)    # jamais retiré
        hier = self.menu_du_jour(plats=[self.plat_a], jours=-1)
        Commande.objects.create(user=self.employe2, menu=hier, plat=self.plat_a, statut='retiree')
        Retrait.objects.create(user=self.employe2, menu=hier, badge_matricule='x', valide_par=self.agent_a,
                               mode='badge', date_retrait=timezone.now() - timedelta(days=1))
        auj = self.menu_du_jour(plats=[self.plat_a])
        Commande.objects.create(user=self.employe2, menu=auj, plat=self.plat_a)                 # à servir : pas un oubli
        url = f'{API}/prestataire/comptoir/historique/'
        debut = (timezone.localdate() - timedelta(days=5)).isoformat()
        c = self.client_pour(self.agent_a)
        r = c.get(url, {'debut': debut}).data
        self.assertEqual((r['total'], r['kpis']['retraits'], r['kpis']['non_retires']), (1, 1, 1))
        r = c.get(url, {'debut': debut, 'statut': 'non_retires'}).data
        self.assertEqual([(x['statut'], x['matricule'], x['heure']) for x in r['resultats']],
                         [('non_retire', self.employe.username, None)])
        r = c.get(url, {'debut': debut, 'statut': 'tous'}).data
        self.assertEqual([x['statut'] for x in r['resultats']], ['retire', 'non_retire'])
        # « Validé par » / mode : retraits seulement
        r = c.get(url, {'debut': debut, 'statut': 'tous', 'mode': 'badge'}).data
        self.assertEqual([x['statut'] for x in r['resultats']], ['retire'])
        self.assertEqual(oubli.statut, 'en_attente')
