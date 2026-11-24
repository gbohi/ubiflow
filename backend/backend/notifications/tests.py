"""Lot 6 : canaux e-mail et push, préférences, périmètres de consultation."""
from unittest import mock

from django.core import mail
from django.test import override_settings

from api.models import PerimetreConsultation, Service
from notifications.models import AppareilMobile, PreferenceNotification
from workflow.tests import Base


@override_settings(EMAIL_HOST='smtp.societe.test', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   FRONTEND_URL='https://ubiflow.societe.test')
class EmailTests(Base):
    def setUp(self):
        super().setUp()
        for u in (self.agent, self.chef, self.daf):
            u.email = f'{u.username}@societe.test'
            u.save()

    def test_validation_attendue_par_email_apres_la_transaction(self):
        pk = self.creer()
        with self.captureOnCommitCallbacks(execute=True):
            self.soumettre(pk)
        destinataires = [m.to[0] for m in mail.outbox]
        self.assertIn('chef@societe.test', destinataires)          # validation attendue (N+1)
        self.assertNotIn('agent@societe.test', destinataires)      # accusé de soumission : application seulement
        m = next(m for m in mail.outbox if m.to == ['chef@societe.test'])
        self.assertIn('https://ubiflow.societe.test/demandes/', m.body)
        self.assertTrue(m.alternatives)  # version HTML

    def test_preferences(self):
        PreferenceNotification.objects.create(user=self.chef, evenement='validation_attendue', email=False, push=False)
        PreferenceNotification.objects.create(user=self.agent, evenement='demande_retournee', email=False, push=False)
        pk = self.creer()
        with self.captureOnCommitCallbacks(execute=True):
            self.soumettre(pk)
        self.assertIn('chef@societe.test', [m.to[0] for m in mail.outbox])  # non désactivable
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            self.agir(pk, self.chef, 'retourner', motif='Préciser')
        self.assertNotIn('agent@societe.test', [m.to[0] for m in mail.outbox])
        self.en(self.agent)
        r = self.client.put('/api/api/notifications/preferences/', [{'evenement': 'validation_attendue', 'email': False},
                                                                     {'evenement': 'demande_approuvee', 'email': False, 'push': True}],
                            format='json')
        evts = {e['evenement']: e for e in r.data['evenements']}
        self.assertTrue(evts['validation_attendue']['email'])
        self.assertFalse(evts['demande_approuvee']['email'])
        self.assertTrue(r.data['email_actif'])

    @override_settings(EMAIL_HOST='')
    def test_sans_smtp_aucun_email(self):
        pk = self.creer()
        with self.captureOnCommitCallbacks(execute=True):
            self.soumettre(pk)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(FIREBASE_CREDENTIALS='/secrets/firebase.json')
class PushTests(Base):
    def test_push_et_appareils(self):
        self.en(self.chef)
        self.assertEqual(self.client.post('/api/api/notifications/appareils/', {'jeton': 'abc', 'plateforme': 'android'},
                                          format='json').status_code, 204)
        reponse = mock.Mock(ok=True, status_code=200, text='{}')
        with mock.patch('notifications.canaux._jeton_firebase', return_value=('jeton-oauth', 'projet-ubiflow')), \
                mock.patch('requests.post', return_value=reponse) as post:
            pk = self.creer()
            with self.captureOnCommitCallbacks(execute=True):
                self.soumettre(pk)
        url, = post.call_args.args
        self.assertIn('projects/projet-ubiflow/messages:send', url)
        self.assertIn('"token": "abc"', post.call_args.kwargs['data'])
        # jeton expiré : appareil désactivé
        with mock.patch('notifications.canaux._jeton_firebase', return_value=('j', 'p')), \
                mock.patch('requests.post', return_value=mock.Mock(ok=False, status_code=404, text='')):
            pk = self.creer()
            with self.captureOnCommitCallbacks(execute=True):
                self.soumettre(pk)
        self.assertFalse(AppareilMobile.objects.get(jeton='abc').actif)


class PerimetreTests(Base):
    def test_direction_limitee_a_son_departement(self):
        self.soumettre(self.creer())                       # agent : Comptabilité (sous Finances)
        dir_user = self.user('dirco', groupes=('direction',))
        self.en(dir_user)
        self.assertEqual(self.client.get('/api/api/demandes/?vue=toutes').data['count'], 1)  # sans périmètre : tout
        PerimetreConsultation.objects.create(user=dir_user, type='departement', departement=self.direction)
        self.assertEqual(self.client.get('/api/api/demandes/?vue=toutes').data['count'], 1)  # Direction ⊃ Finances ⊃ Compta
        autre = Service.objects.create(libelle_service='Commercial')
        PerimetreConsultation.objects.filter(user=dir_user).update(departement=autre)
        self.assertEqual(self.client.get('/api/api/demandes/?vue=toutes').data['count'], 0)
        r = self.client.get('/api/api/tableaux-de-bord/direction/')
        self.assertEqual(next(i['valeur'] for i in r.data['indicateurs'] if i['cle'] == 'soumises'), 0)
        admin = self.user('adm', groupes=('admin',))
        self.en(admin)
        r = self.client.post('/api/api/perimetres-consultation/', {'user': dir_user.pk, 'type': 'agence'}, format='json')
        self.assertEqual(r.status_code, 400)
