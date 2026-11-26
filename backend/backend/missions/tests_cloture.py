"""
Lot 5 : clôture des missions (§9, mode B), modèle « forfait acquis ».

Mission test : per diem 4 j × 25 000 = 100 000 + transport 30 000 + hébergement 60 000
= 190 000 d'avance. À la clôture, le demandeur déclare les dates réelles (et
observations + pièces) ; les forfaits sont repris automatiquement, seules les
indemnités s'ajustent sur la durée réelle. Réel 3 j → retenu 75 000 + 30 000 +
60 000 = 165 000 ; reversement = avance − retenu.
"""
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from demandes.models import Demande, TypePiece
from tresorerie.models import Reversement
from tresorerie.tests import TresorerieBase


class ClotureTests(TresorerieBase):
    def mission_payee(self, montant='190000'):
        pk = self.creer_mission()
        self.soumettre(pk)
        self.approuver(pk)
        self.payer(pk, montant)
        return pk

    def joindre_rapport(self, pk):
        self.en(self.agent)
        r = self.client.post(f'/api/api/demandes/{pk}/documents/', {
            'fichier': SimpleUploadedFile('rapport.pdf', b'%PDF-1.4', content_type='application/pdf'),
            'type_piece': TypePiece.objects.get(code='rapport_mission').pk}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)

    def declarer(self, pk, depart='2026-12-01', retour='2026-12-03'):
        """Le demandeur ne saisit plus que les dates réelles et les observations."""
        self.en(self.agent)
        r = self.client.patch(f'/api/api/demandes/{pk}/cloture/', {'depart_reel': depart, 'retour_reel': retour,
                                                                    'observations': 'Audit réalisé.'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_cloture_avec_reversement(self):
        pk = self.mission_payee()
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier), ('en_attente_cloture', 'payee'))
        c = self.declarer(pk)  # 3 jours réels (sur 4 prévus)
        # indemnités 3×25 000 + transport 30 000 + hébergement 60 000 = 165 000 ; payé 190 000 → 25 000 à rembourser
        self.assertEqual((c['calcul']['jours'], c['calcul']['indemnites'], c['calcul']['transport'], c['calcul']['hotel']),
                         (3, '75000.00', '30000.00', '60000.00'))
        self.assertEqual((c['calcul']['total'], c['calcul']['a_rembourser']), ('165000.00', '25000.00'))
        r = self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('documents', r.data)  # rapport de mission obligatoire
        self.joindre_rapport(pk)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/').status_code, 200)
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/valider/').status_code, 403)  # pas soi-même
        self.en(self.caisse)
        r = self.client.post(f'/api/api/demandes/{pk}/cloture/valider/')
        self.assertEqual(r.status_code, 200, r.data)
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier, d.montant_retenu), ('en_attente_cloture', 'reversement_attendu',
                                                                            Decimal('165000')))
        rev = Reversement.objects.get(demande=d)
        self.assertEqual((rev.montant_du, rev.origine), (Decimal('25000'), 'cloture'))
        self.client.post(f'/api/api/tresorerie/reversements/{rev.pk}/percevoir/', {}, format='multipart')
        d.refresh_from_db()
        self.assertEqual((d.statut, d.statut_financier), ('cloturee', 'soldee'))
        r = self.client.get(f'/api/api/demandes/{pk}/note-frais/')
        self.assertEqual(r.status_code, 200)

    def test_duree_prevue_sans_reversement(self):
        """Durée réelle = durée prévue (4 j) : retenu = avance, aucun reversement."""
        pk = self.mission_payee()
        self.joindre_rapport(pk)
        c = self.declarer(pk, retour='2026-12-04')  # 4 jours = prévu
        self.assertEqual((c['calcul']['jours'], c['calcul']['total'], c['calcul']['a_rembourser']), (4, '190000.00', '0.00'))
        self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.en(self.caisse)
        self.client.post(f'/api/api/demandes/{pk}/cloture/valider/')
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier), ('cloturee', 'soldee'))
        self.assertFalse(Reversement.objects.filter(demande=d).exists())

    def test_duree_plus_longue_plafonnee(self):
        """Durée réelle (5 j) > prévue (4 j) : indemnités plafonnées à 4 j, pas de reste dû auto."""
        pk = self.mission_payee()
        c = self.declarer(pk, retour='2026-12-05')  # 5 jours réels
        self.assertEqual((c['calcul']['jours'], c['calcul']['total'], c['calcul']['a_rembourser']), (4, '190000.00', '0.00'))

    def test_retour_par_le_controleur_et_reste_a_payer(self):
        pk = self.mission_payee('100000')  # partiellement payée
        self.joindre_rapport(pk)
        self.declarer(pk)  # réel 3 j → retenu 165 000
        self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.en(self.caisse)
        self.assertEqual(self.client.get('/api/api/missions/clotures/').data[0]['id'], pk)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/retourner/', {}, format='json').status_code, 400)
        self.client.post(f'/api/api/demandes/{pk}/cloture/retourner/', {'motif': 'Joindre le rapport détaillé'}, format='json')
        self.declarer(pk)  # le demandeur peut de nouveau modifier
        self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.en(self.caisse)
        self.client.post(f'/api/api/demandes/{pk}/cloture/valider/')
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.montant_retenu, d.solde, d.statut_financier), (Decimal('165000'), Decimal('65000'),
                                                                           'partiellement_payee'))
        self.payer(pk, '80000', attendu=400)  # plus que le reste dû (65 000)
        self.payer(pk, '65000')
        d.refresh_from_db()
        self.assertEqual((d.statut, d.statut_financier), ('cloturee', 'soldee'))

    def test_saisie_reservee_au_demandeur(self):
        pk = self.mission_payee()
        self.en(self.autre)
        self.assertEqual(self.client.patch(f'/api/api/demandes/{pk}/cloture/', {'observations': 'x'},
                                           format='json').status_code, 403)

    def test_rappel_de_cloture(self):
        from django.core.management import call_command
        from notifications.models import Notification
        pk = self.creer_mission(depart_le='2026-01-05T08:00:00', retour_le='2026-01-06T18:00:00')
        self.soumettre(pk)
        self.approuver(pk)
        call_command('taches_planifiees')
        self.assertEqual(Notification.objects.filter(destinataire=self.agent, evenement='rappel_cloture').count(), 1)
        call_command('taches_planifiees')  # une fois par semaine au plus
        self.assertEqual(Notification.objects.filter(destinataire=self.agent, evenement='rappel_cloture').count(), 1)
